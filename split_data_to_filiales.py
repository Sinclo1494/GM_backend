"""
Copy the central GM data into the per-filiale databases.

The application is being migrated from a single central database (GM) to one
PostgreSQL database per affiliate (gm_a, gm_c, gm_e, gm_g, gm_k, gm_l, gm_m,
gm_p, gm_r, gm_t).

Until this script has run, every affiliate database is empty while all the
business data lives in the central "GM" database, so a user assigned to an
affiliate would see empty lists.

Split rules
------------
Reference data (identical for every affiliate) is copied to every database:

    api_filiale, api_categorie_gm, api_famille_materiel,
    api_sous_famille_materiel, api_marque_materiel, api_type_marque,
    api_type_affectation, api_type_situation, api_type_etat_materiel

Business data is partitioned by affiliate:

    api_site                  -> site.code_filiale
    api_grand_materiel        -> materiel.code_filiale_g, or any affectation
                                 belonging to the affiliate (a materiel
                                 transferred to another affiliate is kept in
                                 both databases, as the analysis reports it
                                 per affectation)
    api_affectation_materiel  -> affectation.code_filiale_mere
    api_situation_materiel    -> situation.affectation.code_filiale_mere
    api_pointage              -> pointage.affectation.code_filiale_mere
    api_regularisation_gm     -> regularisation.code_site.code_filiale
    api_regularisation_mois_gm2 -> no affiliate discriminator, copied as is

The ``auth_user`` rows are copied as well: they are pure foreign-key anchors
(the application always reads the users from the central database, see
``api.multidb.CENTRAL_DB_MODELS``) but ``user_id`` cannot be NULL.

The central database is never modified: this script only reads from it.

Usage
-----
    python split_data_to_filiales.py --dry-run     # show the plan only
    python split_data_to_filiales.py                # copy the missing rows
    python split_data_to_filiales.py --force        # re-copy everything
"""

import argparse
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.apps import apps  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.db import connections, transaction  # noqa: E402

from api.multidb import CENTRAL_DB_MODELS, filiale_db_name  # noqa: E402


BATCH_SIZE = 2000

# Tables that hold the same rows for every affiliate.  The order matters:
# a row may reference a table listed before it (api_filiale -> api_entreprise,
# api_division -> api_filiale).
SHARED_MODELS = [
    ("api", "entreprise"),
    ("api", "filiale"),
    ("api", "division"),
    ("api", "famille_structures"),
    ("api", "categorie_gm"),
    ("api", "famille_materiel"),
    ("api", "sous_famille_materiel"),
    ("api", "marque_materiel"),
    ("api", "type_marque"),
    ("api", "type_affectation"),
    ("api", "type_situation"),
    ("api", "type_etat_materiel"),
]

# Business tables and the queryset filter that selects the rows of one
# affiliate.  The filter is expressed with the ORM so that the custom
# db_column names are handled by Django.  ``distinct`` is required as soon as
# the filter goes through a reverse relation (a materiel can match twice).
SPLIT_PLAN = [
    ("api", "site", lambda code: {"code_filiale__code_filiale": code}, False),
    (
        "api",
        "grand_materiel",
        lambda code: {
            "$or": [
                {"code_filiale_g__code_filiale": code},
                {"affectations__code_filiale_mere__code_filiale": code},
            ]
        },
        True,
    ),
    (
        "api",
        "affectation_materiel",
        lambda code: {"code_filiale_mere__code_filiale": code},
        False,
    ),
    (
        "api",
        "situation_materiel",
        lambda code: {"affectation_id__code_filiale_mere__code_filiale": code},
        False,
    ),
    (
        "api",
        "pointage",
        lambda code: {"affectation_id__code_filiale_mere__code_filiale": code},
        False,
    ),
    (
        "api",
        "regularisation_gm",
        lambda code: {"code_site__code_filiale__code_filiale": code},
        False,
    ),
    ("api", "regularisation_mois_gm2", lambda code: {}, False),
]


def build_queryset(model, filters, distinct=False):
    """Return the source queryset of ``model`` for the given filter mapping."""
    qs = model.objects.using("default").all()
    if not filters:
        return qs
    or_filters = filters.get("$or")
    if or_filters:
        from django.db.models import Q

        query = Q()
        for part in or_filters:
            query |= Q(**part)
        qs = qs.filter(query)
    else:
        qs = qs.filter(**filters)
    if distinct:
        qs = qs.distinct()
    return qs


def copy_rows(model, source_qs, target_alias, delete_target=False):
    """Copy every row of ``source_qs`` into ``target_alias``."""
    fields = [f for f in model._meta.concrete_fields]
    attnames = [f.attname for f in fields]

    if delete_target:
        model.objects.using(target_alias).all().delete()

    copied = 0
    batch = []
    for src in source_qs.iterator(chunk_size=BATCH_SIZE):
        batch.append(model(**{att: getattr(src, att) for att in attnames}))
        if len(batch) >= BATCH_SIZE:
            model.objects.using(target_alias).bulk_create(batch, batch_size=BATCH_SIZE)
            copied += len(batch)
            batch = []
    if batch:
        model.objects.using(target_alias).bulk_create(batch, batch_size=BATCH_SIZE)
        copied += len(batch)
    return copied


def reset_sequence(model, target_alias):
    """Advance the primary key sequence of ``model`` in ``target_alias``."""
    table = model._meta.db_table
    pk_column = model._meta.pk.column
    sql = (
        f"SELECT setval(pg_get_serial_sequence('{table}', '{pk_column}'), "
        f"COALESCE((SELECT MAX({model._meta.pk.column}) FROM {table}), 1), true)"
    )
    with connections[target_alias].cursor() as cursor:
        cursor.execute(sql)


def table_columns(alias, table):
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s",
            [table],
        )
        return {row[0] for row in cursor.fetchall()}


def check_schema(target_alias, model):
    """Make sure the affiliate table has the same columns as the central one."""
    table = model._meta.db_table
    central = table_columns("default", table)
    target = table_columns(target_alias, table)
    missing = central - target
    if missing:
        raise RuntimeError(
            f"Column mismatch on '{table}' in '{target_alias}': missing {sorted(missing)}"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="only show the plan")
    parser.add_argument("--force", action="store_true", help="re-copy rows that are already present")
    parser.add_argument(
        "--filiale",
        action="append",
        default=None,
        help="restrict the copy to the given affiliate code (repeatable)",
    )
    args = parser.parse_args(argv)

    from django.conf import settings

    codes = list(settings.FILIALE_DATABASES.keys())
    if args.filiale:
        unknown = [c for c in args.filiale if c not in codes]
        if unknown:
            raise SystemExit(f"Unknown affiliate code(s): {unknown}")
        codes = args.filiale

    total_copied = 0

    for code in codes:
        target_alias = filiale_db_name(code)
        print("=" * 72)
        print(f"[{code}] -> {target_alias} ({settings.FILIALE_DATABASES[code]})")

        # 1. The users, as foreign-key anchors (the application reads them
        #    from the central database).
        check_schema(target_alias, User)
        users = User.objects.using("default").all()
        expected = users.count()
        current = User.objects.using(target_alias).count()
        if not (current == expected and not args.force):
            if not args.dry_run:
                copied = copy_rows(User, users, target_alias, delete_target=True)
                reset_sequence(User, target_alias)
                total_copied += copied
                print(f"  + {'auth_user':<28} {copied:>7} (copied)")
            else:
                print(f"  + {'auth_user':<28} {expected:>7} (to copy)")

        # 2. Reference data + foreign-key anchors.
        for app_label, model_name in SHARED_MODELS:
            model = apps.get_model(app_label, model_name)
            check_schema(target_alias, model)
            source = model.objects.using("default").all()
            expected = source.count()
            current = model.objects.using(target_alias).count()
            if current == expected and not args.force:
                print(f"  = {model_name:<28} {current:>7} (already up to date)")
                continue
            if args.dry_run:
                print(f"  + {model_name:<28} {expected:>7} (to copy)")
                continue
            copied = copy_rows(model, source, target_alias, delete_target=True)
            reset_sequence(model, target_alias)
            total_copied += copied
            print(f"  + {model_name:<28} {copied:>7} (copied)")

        # 3. Business data, partitioned by affiliate.
        for app_label, model_name, filter_builder, distinct in SPLIT_PLAN:
            model = apps.get_model(app_label, model_name)
            check_schema(target_alias, model)
            source = build_queryset(model, filter_builder(code), distinct)
            expected = source.count()
            current = model.objects.using(target_alias).count()
            if current == expected and not args.force:
                print(f"  = {model_name:<28} {current:>7} (already up to date)")
                continue
            if args.dry_run:
                print(f"  + {model_name:<28} {expected:>7} (to copy)")
                continue
            with transaction.atomic(using=target_alias):
                copied = copy_rows(model, source, target_alias, delete_target=True)
                reset_sequence(model, target_alias)
            total_copied += copied
            print(f"  + {model_name:<28} {copied:>7} (copied)")

    print("=" * 72)
    print(f"Total rows copied: {total_copied}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
