from django.db import models


class Regularisation_GM(models.Model):
    code_regularisation = models.CharField(max_length=100, unique=True)
    code_site = models.ForeignKey(
        "Site",
        on_delete=models.PROTECT,
        db_column="code_site",
        related_name="regularisations",
    )
    montant_regularisation = models.DecimalField(max_digits=10, decimal_places=2)
    mmaa = models.DateField()
    observation = models.TextField()
    est_bloque = models.BooleanField(default=False)
    user_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code_regularisation
