from django.db import models


class Regularisation_Mois_GM2(models.Model):
    code_regularisation = models.CharField(max_length=100, unique=True)
    montant_regularisation = models.DecimalField(max_digits=10, decimal_places=2)
    est_bloque = models.BooleanField(default=False)
    user_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code_regularisation
