from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model()


class Regularisation_GM(models.Model):
    code_site = models.ForeignKey(
        "Site",
        on_delete=models.PROTECT,
        db_column="code_site",
        to_field="code_site",
        related_name="regularisations",
    )
    mmaa = models.DateField()
    montant_regularisation = models.DecimalField(max_digits=20, decimal_places=4)
    observation = models.TextField(blank=True,null=True)
    est_bloque = models.BooleanField(default=False)
    user_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,default=1
    )
    date_modification = models.DateTimeField(null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="unique_site_mmaa",
                fields=["code_site","mmaa"],
            )
        ]
    def __str__(self):
        return (f"{self.code_site} - {self.mmaa}")
# Confirmation workflow
    STATUS_CHOICES = (
        ('PENDING', 'En attente'),
        ('CONFIRMED', 'Confirmé'),
        ('REJECTED', 'Rejeté'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='CONFIRMED')
    imported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_imported')
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_confirmed')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_rejected')
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    import_batch_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
