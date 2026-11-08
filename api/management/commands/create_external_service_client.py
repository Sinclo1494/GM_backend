from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from api.models import ExternalServiceClient
from api.services.external_service_credentials import (
    generate_client_id,
    generate_client_secret,
    hash_secret,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Register an external service account (M2M)."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=False, help="Human-readable service name")
        parser.add_argument("--created-by", default=None, help="Username of creator")
        parser.add_argument("--rotate", default=None, help="client_id to rotate secret for")

    def handle(self, *args, **options):
        rotate_id = options["rotate"]
        if rotate_id:
            try:
                client = ExternalServiceClient.objects.get(client_id=rotate_id)
            except ExternalServiceClient.DoesNotExist:
                raise CommandError(f"Service client '{rotate_id}' not found.")
            secret = generate_client_secret()
            client.client_secret_hash = hash_secret(secret)
            client.save(update_fields=["client_secret_hash", "updated_at"])
            self.stdout.write(self.style.SUCCESS("Secret rotated."))
            self.stdout.write(f"Client ID: {client.client_id}")
            self.stdout.write(f"Client Secret (shown once): {secret}")
            self.stdout.write(self.style.WARNING("Store this secret securely. It will not be shown again."))
            return

        name = (options["name"] or "").strip()
        if not name:
            raise CommandError("--name is required when creating a service account.")

        created_by = None
        if options["created_by"]:
            try:
                created_by = User.objects.get(username=options["created_by"])
            except User.DoesNotExist:
                raise CommandError(f"User '{options['created_by']}' not found.")

        client_id = generate_client_id()
        secret = generate_client_secret()
        client = ExternalServiceClient.objects.create(
            name=name,
            client_id=client_id,
            client_secret_hash=hash_secret(secret),
            is_active=True,
            created_by=created_by,
        )
        self.stdout.write(self.style.SUCCESS("Service account created."))
        self.stdout.write(f"Client ID: {client.client_id}")
        self.stdout.write(f"Client Secret (shown once): {secret}")
        self.stdout.write(self.style.WARNING("Store these credentials securely. The secret will not be shown again."))
