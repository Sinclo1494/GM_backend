import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from api.models import ExternalServiceClient
from api.services.external_service_credentials import generate_client_id, generate_client_secret, hash_secret
from rest_framework_simplejwt.tokens import AccessToken


class ExternalServiceAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.secret = generate_client_secret()
        self.client_id = generate_client_id()
        self.obj = ExternalServiceClient.objects.using("default").create(
            name="svc",
            client_id=self.client_id,
            client_secret_hash=hash_secret(self.secret),
            is_active=True,
        )

    def test_success(self):
        resp = self.client.post("/api/auth/service-token/", {"client_id": self.client_id, "client_secret": self.secret}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.data)
        self.assertEqual(resp.data["token_type"], "Bearer")
        self.assertEqual(resp.data["expires_in"], 1800)
        token = AccessToken(resp.data["access"])
        self.assertEqual(token["service_type"], "external_service")
        self.assertEqual(token["client_id"], self.client_id)
        self.assertEqual(str(token["service_client_id"]), str(self.obj.id))

    def test_unknown_client(self):
        resp = self.client.post("/api/auth/service-token/", {"client_id": "nope", "client_secret": self.secret}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_wrong_secret(self):
        resp = self.client.post("/api/auth/service-token/", {"client_id": self.client_id, "client_secret": "wrong"}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_inactive(self):
        self.obj.is_active = False
        self.obj.save(using="default")
        resp = self.client.post("/api/auth/service-token/", {"client_id": self.client_id, "client_secret": self.secret}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_expired(self):
        self.obj.expires_at = timezone.now() - timedelta(minutes=1)
        self.obj.save(using="default")
        resp = self.client.post("/api/auth/service-token/", {"client_id": self.client_id, "client_secret": self.secret}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_missing(self):
        for payload in ({}, {"client_id": self.client_id}, {"client_secret": self.secret}, {"client_id": "", "client_secret": ""}):
            resp = self.client.post("/api/auth/service-token/", payload, format="json")
            self.assertEqual(resp.status_code, 401)

    def test_method(self):
        resp = self.client.get("/api/auth/service-token/")
        self.assertEqual(resp.status_code, 405)

    def test_last_used_updated(self):
        self.client.post("/api/auth/service-token/", {"client_id": self.client_id, "client_secret": self.secret}, format="json")
        self.obj.refresh_from_db(using="default")
        self.assertIsNotNone(self.obj.last_used_at)
