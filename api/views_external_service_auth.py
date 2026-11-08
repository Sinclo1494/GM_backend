from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from api.models import ExternalServiceClient
from api.services.external_service_credentials import verify_secret


class ServiceTokenThrottle(AnonRateThrottle):
    rate = "100/min"


class ServiceAccessToken(AccessToken):
    lifetime = timedelta(minutes=30)


class ServiceTokenView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ServiceTokenThrottle]

    def post(self, request):
        client_id = (request.data.get("client_id") or "").strip()
        client_secret = request.data.get("client_secret") or ""

        if not client_id or not client_secret:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            client = ExternalServiceClient.objects.using("default").get(client_id=client_id)
        except ExternalServiceClient.DoesNotExist:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        if not client.is_active:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        if client.expires_at is not None and client.expires_at <= timezone.now():
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        if not verify_secret(client_secret, client.client_secret_hash):
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        token = ServiceAccessToken()
        token["service_type"] = "external_service"
        token["service_client_id"] = str(client.id)
        token["client_id"] = client.client_id

        client.last_used_at = timezone.now()
        client.save(using="default", update_fields=["last_used_at", "updated_at"])

        return Response(
            {
                "access": str(token),
                "token_type": "Bearer",
                "expires_in": 1800,
            },
            status=status.HTTP_200_OK,
        )

    def get(self, request):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
