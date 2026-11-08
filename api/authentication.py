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
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from django.utils import timezone

from api.multidb import set_current_filiale
from api.permissions import resolve_filiale_code
from api.models import ExternalServiceClient


class ServicePrincipal:
    def __init__(self, client):
        self.id = client.id
        self.service_client_id = client.id
        self.client_id = client.client_id
        self.service_name = client.name
        self.is_authenticated = True
        self.is_anonymous = False
        self.is_external_service = True
        self.is_staff = False
        self.is_superuser = False

    def __str__(self):
        return f"service:{self.client_id}"


class ExternalServiceJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None
        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None
        try:
            validated_token = self.get_validated_token(raw_token)
        except (InvalidToken, TokenError):
            return None
        if validated_token.get("service_type") != "external_service":
            return None
        client_id = validated_token.get("service_client_id")
        if not client_id:
            raise InvalidToken("Missing service client ID.")
        try:
            client = ExternalServiceClient.objects.using("default").get(id=client_id)
        except ExternalServiceClient.DoesNotExist:
            raise InvalidToken("Service client not found.")
        if not client.is_active:
            raise InvalidToken("Service client inactive.")
        if client.expires_at is not None and client.expires_at <= timezone.now():
            raise InvalidToken("Service client expired.")
        principal = ServicePrincipal(client)
        set_current_filiale(None)
        return (principal, validated_token)


class FilialeAwareJWTAuthentication(JWTAuthentication):
    """JWT authentication that also binds the request to a affiliate database."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user = result[0]
            set_current_filiale(resolve_filiale_code(user, request))
        return result
