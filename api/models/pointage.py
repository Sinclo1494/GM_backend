from django.db import models


class Pointage(models.Model):
    code_pointage = models.CharField(max_length=100, unique=True)
    code_affectation = models.ForeignKey(
        "Affectation_Materiel",
        on_delete=models.PROTECT,
        db_column="code_affectation",
        related_name="pointages",
    )
    mmaa = models.DateField()
    taux_location = models.DecimalField(max_digits=10, decimal_places=5)
    heures_service = models.DecimalField(max_digits=5, decimal_places=1)
    heures_chomage = models.DecimalField(max_digits=5, decimal_places=1)
    heures_panne = models.DecimalField(max_digits=5, decimal_places=1)
    potentiel = models.DecimalField(max_digits=5, decimal_places=1)
    montant_service = models.DecimalField(max_digits=10, decimal_places=2)
    montant_chomage = models.DecimalField(max_digits=10, decimal_places=2)
    montant_panne = models.DecimalField(max_digits=10, decimal_places=2)
    code_site = models.ForeignKey(
        "Site",
        on_delete=models.PROTECT,
        db_column="code_site",
        related_name="pointages",
    )
    est_bloque = models.BooleanField(default=False)
    user_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code_pointage
