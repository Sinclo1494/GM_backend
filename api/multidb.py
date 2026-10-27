"""
Multi-database routing for the per-filiale database topology.

Topology:
  - "default"          : central admin database (users, auth, Filiale, config).
  - "filiale_<code>"   : one physical PostgreSQL database per filiale
                         (reference data + transactional data).

Routing rules:
  - CENTRAL_DB_MODELS  -> always "default".
  - Any other model    -> routed to the authenticated user's filiale database
                          resolved from request state (server-side, never client).
  - Fail closed: if a filiale-scoped model has no resolved filiale, raise
    DatabaseRoutingError instead of silently falling back to "default".

The current filiale is stored in a thread-local that is scoped to a single
request (set by FilialeRoutingMiddleware, cleared in a finally block). It is
NEVER stored in a process-global variable and settings.DATABASES is never
mutated at runtime.
"""

import threading

import logging

from contextlib import contextmanager

from django.db import router as django_router

from django.conf import settings


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request-scoped filiale store (thread-local, cleared per request)
# ---------------------------------------------------------------------------

_current_filiale = threading.local()


class DatabaseRoutingError(Exception):
    """Raised when a filiale-scoped model cannot be routed to a database."""


def set_current_filiale(code_filiale):
    """Set the filiale for the current request/thread."""
    _current_filiale.value = code_filiale


def get_current_filiale():
    """Return the filiale code for the current request/thread, or None."""
    return getattr(_current_filiale, "value", None)


def clear_current_filiale():
    """Clear the filiale for the current request/thread."""
    _current_filiale.value = None


def filiale_db_name(code_filiale):
    """Return the Django DATABASES key for a filiale code."""
    return f"filiale_{code_filiale}"


def get_filiale_db(filiale_code):
    """
    Validate a filiale code and return its Django DATABASES key.

    Raises DatabaseRoutingError if the code is missing or its database is
    not registered in settings.DATABASES (fail closed).
    """
    if not filiale_code:
        raise DatabaseRoutingError(
            "Aucun code de filiale fourni pour l'import/validation."
        )
    db = filiale_db_name(filiale_code)
    if db not in settings.DATABASES:
        raise DatabaseRoutingError(
            f"Base de données filiale '{db}' introuvable pour le code "
            f"'{filiale_code}' (non enregistrée dans settings.DATABASES)."
        )
    return db


def filiale_code_for_db(db_name):
    """
    Return the affiliate code owning the given ``filiale_<code>`` database
    alias, or None when the alias is not a registered affiliate database.
    """
    for code in settings.FILIALE_DATABASES:
        if filiale_db_name(code) == db_name:
            return code
    return None


@contextmanager
def affiliate_routing(code_filiale):
    """
    Temporarily route affiliate-scoped models to ``code_filiale``'s database.

    Django resolves the database of some operations through the router
    instead of the queryset it came from:

    - ``Model.full_clean()`` checks foreign keys (``clean_fields`` ->
      ``ForeignKey.validate``) and unique constraints against the database
      the router selects for the related model.
    - ``Model.save()`` without an explicit ``using=`` writes to the database
      the router selects for the model.

    The router always answers with the *request-scoped* affiliate, which is
    the affiliate of the authenticated user.  An administrator confirming or
    rejecting a batch that was imported for another affiliate would then
    validate the rows against (and write them to) the wrong database.

    This context manager pins the routing to the affiliate that owns the
    rows for the duration of the block, and restores the previous routing
    afterwards.
    """
    previous = get_current_filiale()
    set_current_filiale(code_filiale)
    try:
        yield
    finally:
        set_current_filiale(previous)


# ---------------------------------------------------------------------------
# Central vs filiale model sets
# ---------------------------------------------------------------------------

# Models that always live in the central "default" database.
# NOTE: the User model is Django's default django.contrib.auth.models.User,
# so its label is "auth.user" (NOT "api.user"). Auth-related contrib models
# must be listed here too, otherwise login / token endpoints fail with
# DatabaseRoutingError because they run before FilialeRoutingMiddleware.
CENTRAL_DB_MODELS = {
    "auth.user",
    "auth.group",
    "auth.permission",
    "contenttypes.contenttype",
    "sessions.session",
    "api.userprofile",
    "api.filiale",
    "api.entreprise",
    "api.division",
    "api.famille_structures",
    "api.journal",
    "api.notification",
}

# All remaining business models live in each filiale database.
# These are routed through the fail-closed router.

# ---------------------------------------------------------------------------
# Models that support import batches / confirmation workflow
# ---------------------------------------------------------------------------

PENDING_MODEL_KEYS = [
    "pointage",
    "grand_materiel",
    "affectation_materiel",
    "situation_materiel",
    "site",
    "famille_materiel",
    "sous_famille_materiel",
    "marque_materiel",
    "type_marque",
    "categorie_gm",
    "regularisation_gm",
]


def get_pending_models():
    """
    Return [(key, model_class)] for every model that supports the
    import-batch confirmation workflow. All are filiale-scoped.
    """
    from django.apps import apps

    return [(key, apps.get_model("api", key)) for key in PENDING_MODEL_KEYS]


def find_filiale_db_for_batch(batch_id):
    """
    Search every filiale database for PENDING records carrying the given
    import_batch_id. Return the Django DATABASES key of the filiale that owns
    the batch, or None if no such batch exists.

    A batch belongs to a single filiale database (an import targets one
    filiale), so at most one database will contain matching records.
    """
    from django.conf import settings

    for _code, _db_name in settings.FILIALE_DATABASES.items():
        db = filiale_db_name(_code)
        for _key, ModelClass in get_pending_models():
            if (
                ModelClass.objects.using(db)
                .filter(import_batch_id=batch_id, status="PENDING")
                .exists()
            ):
                return db
    return None


# ---------------------------------------------------------------------------
# Database router
# ---------------------------------------------------------------------------

class FailClosedDatabaseRouter:
    """
    Route filiale-scoped models to the authenticated user's filiale database.
    Central models go to "default".

    When no affiliate can be resolved (the user has no affiliate assigned and
    did not request one), the router falls back to the central "default"
    database when ``settings.FILIALE_ROUTING_FALLBACK_TO_CENTRAL`` is True.
    Set that flag to False to get the strict fail-closed behaviour.
    """

    def _resolve_db(self, model):
        label = f"{model._meta.app_label}.{model._meta.model_name}".lower()

        # Central models -> default database.
        if label in CENTRAL_DB_MODELS:
            return "default"

        # Filiale-scoped models -> user's filiale database.
        code = get_current_filiale()
        if code:
            db = filiale_db_name(code)
            if db in settings.DATABASES:
                return db
            logger.warning(
                "Affiliate database '%s' for code '%s' is not registered in "
                "settings.DATABASES; falling back to the central database.",
                db,
                code,
            )
        else:
            logger.warning(
                "No affiliate database resolved for model '%s'; using the "
                "central database.",
                label,
            )

        if getattr(settings, "FILIALE_ROUTING_FALLBACK_TO_CENTRAL", False):
            return "default"

        raise DatabaseRoutingError(
            "No filiale database resolved for model "
            f"'{label}'; refusing to fall back to 'default'. "
            "Set the current filiale via set_current_filiale() before "
            "querying filiale-scoped models."
        )

    def db_for_read(self, model, **hints):
        return self._resolve_db(model)

    def db_for_write(self, model, **hints):
        return self._resolve_db(model)

    @staticmethod
    def _is_central_instance(obj):
        """
        Return True when the object belongs to a central model
        (auth.user, api.filiale, api.journal, ...).
        """
        meta = getattr(obj, "_meta", None)
        if meta is None:
            return False
        label = f"{meta.app_label}.{meta.model_name}".lower()
        return label in CENTRAL_DB_MODELS

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow the relations that are valid in the per-filiale topology.

        - Same database on both sides: always allowed.
        - One side unbound: always allowed (Django resolves it later).
        - Different databases: allowed only when one side is a CENTRAL
          model. Central tables (auth_user, api_filiale, ...) are
          replicated with identical primary keys in every filial
          database, so the referenced row exists on the other side.
        - Two filial-scoped models bound to two different filial
          databases: DENIED, a row of affiliate A must never reference
          a row of affiliate B.
        """
        db1 = getattr(getattr(obj1, "_state", None), "db", None)
        db2 = getattr(getattr(obj2, "_state", None), "db", None)

        if not (db1 and db2) or db1 == db2:
            return True

        return (
            self._is_central_instance(obj1)
            or self._is_central_instance(obj2)
        )

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Migrations are applied explicitly per database via
        backend/migrate_all_filiales.py (manage.py migrate --database=<db>).
        Returning None lets Django's default --database handling decide.
        """
        return None
