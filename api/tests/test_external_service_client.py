import uuid

from django.test import TestCase
from django.contrib.auth import get_user_model

from api.models import ExternalServiceClient
from api.services.external_service_credentials import (
    generate_client_id,
    generate_client_secret,
    hash_secret,
    verify_secret,
)

User = get_user_model()


class ExternalServiceClientTests(TestCase):
    def test_create_and_hash(self):
        client_id = generate_client_id()
        secret = generate_client_secret()
        obj = ExternalServiceClient.objects.create(
            name="svc",
            client_id=client_id,
            client_secret_hash=hash_secret(secret),
            is_active=True,
        )
        self.assertTrue(verify_secret(secret, obj.client_secret_hash))
        self.assertFalse(verify_secret("wrong", obj.client_secret_hash))

    def test_unique_client_id(self):
        ids = {generate_client_id() for _ in range(100)}
        self.assertEqual(len(ids), 100)

    def test_inactive(self):
        obj = ExternalServiceClient.objects.create(
            name="svc2",
            client_id=generate_client_id(),
            client_secret_hash=hash_secret(generate_client_secret()),
            is_active=False,
        )
        self.assertFalse(obj.is_active)

    def test_expiration_field(self):
        from django.utils import timezone
        import datetime
        future = timezone.now() + datetime.timedelta(days=1)
        obj = ExternalServiceClient.objects.create(
            name="svc3",
            client_id=generate_client_id(),
            client_secret_hash=hash_secret(generate_client_secret()),
            expires_at=future,
        )
        self.assertIsNotNone(obj.expires_at)

    def test_rotation(self):
        secret = generate_client_secret()
        obj = ExternalServiceClient.objects.create(
            name="svc4",
            client_id=generate_client_id(),
            client_secret_hash=hash_secret(secret),
        )
        new_secret = generate_client_secret()
        obj.client_secret_hash = hash_secret(new_secret)
        obj.save()
        self.assertTrue(verify_secret(new_secret, obj.client_secret_hash))
        self.assertFalse(verify_secret(secret, obj.client_secret_hash))

    def test_no_plaintext_exposure(self):
        secret = generate_client_secret()
        obj = ExternalServiceClient.objects.create(
            name="svc5",
            client_id=generate_client_id(),
            client_secret_hash=hash_secret(secret),
        )
        self.assertNotEqual(obj.client_secret_hash, secret)
        self.assertNotIn(secret, obj.client_secret_hash)
