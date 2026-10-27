"""
Middleware that resolves the authenticated user's filiale and stores it in the
request-scoped thread-local used by FailClosedDatabaseRouter.

Resolution is server-side only: the affiliate is read from the user's
UserProfile -> Filiale relationship, never from client-supplied parameters
(except for the explicit ``?filiale=`` override, which is validated against
the user's allowed affiliates).

- Filiale user: current filiale = the Filiale linked to their profile.
- All-filiales user (``administration.all_filiales`` permission, non-superuser):
  current filiale = the affiliate supplied in the request's ``filiale`` query
  parameter when present, otherwise the user's own profile affiliate.
- Superuser: no default affiliate, but the same ``?filiale=`` override works.

IMPORTANT: this middleware runs BEFORE DRF authenticates the request, so for
JWT requests ``request.user`` is still an ``AnonymousUser`` here.  The
authoritative resolution happens in
``api.authentication.FilialeAwareJWTAuthentication``, right after the token
has been validated.  This middleware only handles session-authenticated
requests and guarantees that the thread-local is always cleared at the end of
the request.

It also releases the affiliate connections opened while serving the request
(see ``release_filiale_connections``): all the aliases share the same
PostgreSQL server's ``max_connections`` budget, so a connection left behind
by a slow request can starve every other endpoint.
"""

from django.conf import settings
from django.db import connections

from api.multidb import set_current_filiale, clear_current_filiale
from api.permissions import resolve_filiale_code


def release_filiale_connections():
    """
    Close the affiliate connections opened while serving the request.

    All the aliases point at the same PostgreSQL server, whose
    ``max_connections`` budget is shared by the central database and the ten
    affiliate databases.  A request may open several affiliate connections
    (the all-filiales branch of the analysis views queries every affiliate in
    turn), and Django only reaps a connection when the thread that owns it
    handles another request, so a connection owned by a slow thread outlives
    ``CONN_MAX_AGE`` and stays counted against the server budget.

    Releasing them here, in the middleware's ``finally`` block, guarantees
    they are given back even when the request failed.  The central
    ``default`` connection is left alone: it is bounded by the worker thread
    count and Django closes it on its own schedule.
    """
    for code in settings.FILIALE_DATABASES:
        connections[f"filiale_{code}"].close()


class FilialeRoutingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        code_filiale = None

        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            # Session-authenticated request: the user is already known here.
            code_filiale = resolve_filiale_code(user, request)

        set_current_filiale(code_filiale)

        try:
            response = self.get_response(request)
        finally:
            clear_current_filiale()
            release_filiale_connections()

        return response
