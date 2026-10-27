"""
Authentication classes.

The affiliate ("filiale") of a request is resolved *after* the JWT has been
validated, because DRF only authenticates the request inside the view
(``APIView.initial`` -> ``perform_authentication``), while Django middleware
runs long before that.

``FilialeRoutingMiddleware`` therefore sees an ``AnonymousUser`` for every
JWT request and used to resolve ``code_filiale = None``, which made
``FailClosedDatabaseRouter`` raise ``DatabaseRoutingError`` on every
affiliate-scoped endpoint (``/api/categorie-gm/`` and friends).

``FilialeAwareJWTAuthentication`` performs the same resolution at the right
moment: right after the token has been validated and the user is known.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication

from api.multidb import set_current_filiale
from api.permissions import resolve_filiale_code


class FilialeAwareJWTAuthentication(JWTAuthentication):
    """JWT authentication that also binds the request to a affiliate database."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user = result[0]
            set_current_filiale(resolve_filiale_code(user, request))
        return result
