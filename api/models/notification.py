from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Notification(models.Model):
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(
        max_length=50,
        choices=[
            ("PENDING_IMPORT", "Import en attente"),
            ("IMPORT_REJECTED", "Import rejeté"),
            ("IMPORT_CONFIRMED", "Import confirmé"),
        ],
        default="PENDING_IMPORT",
    )
    related_object_type = models.CharField(max_length=100, null=True, blank=True)
    related_object_id = models.CharField(max_length=100, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications",
    )
    import_model = models.CharField(max_length=255, null=True, blank=True)
    record_count = models.IntegerField(null=True, blank=True)
    import_datetime = models.DateTimeField(null=True, blank=True)
    rejection_datetime = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    confirmation_datetime = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.title
