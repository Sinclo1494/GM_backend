from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model()


class Pointage(models.Model):
    affectation_id = models.ForeignKey(
        "Affectation_Materiel",
        on_delete=models.PROTECT,
        to_field="id",
        db_column="affectation_id",
        related_name="pointages_ids",
    )
    mmaa = models.DateField()
    taux_location = models.DecimalField(max_digits=20, decimal_places=7,null=True,blank=True)
    heures_service = models.DecimalField(max_digits=10, decimal_places=1)
    heures_chomage = models.DecimalField(max_digits=10, decimal_places=1)
    heures_panne = models.DecimalField(max_digits=10, decimal_places=1)
    potentiel = models.DecimalField(max_digits=5, decimal_places=1)
    montant_service = models.DecimalField(max_digits=20, decimal_places=7,null=True,blank=True)
    montant_chomage = models.DecimalField(max_digits=20, decimal_places=7,null=True,blank=True)
    montant_panne = models.DecimalField(max_digits=20, decimal_places=7,null=True,blank=True)
    est_bloque = models.BooleanField(default=False)
    user_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,default=1
    )
    date_modification = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="unique_affectationId_mmaa",
                fields=["affectation_id","mmaa"],
            )
        ]

    def __str__(self):
        return  f"{self.affectation_id} - {self.mmaa}"
