import uuid

from django.conf import settings
from django.db import models


class ExternalServiceClient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    client_id = models.CharField(max_length=64, unique=True)
    client_secret_hash = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="external_service_clients",
    )

    # Per-client filiale scoping for the external API.
    #
    # Empty = NO access. A client must be explicitly assigned at least one
    # filiale to read data. Existing clients are back-filled to all ten
    # configured filiales by the data migration that accompanies this field,
    # so their behaviour is unchanged.
    #
    # ``Filiale`` is a central model (routed to "default"), and so is this
    # model; the M2M through table therefore lives in the central database
    # alongside both sides of the relation.
    allowed_filiales = models.ManyToManyField(
        "Filiale",
        blank=True,
        related_name="external_service_clients",
        help_text="Filiales autorisées pour ce service. Aucune = aucun accès.",
    )

    class Meta:
        app_label = "api"
        db_table = "api_externalserviceclient"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.client_id})"
