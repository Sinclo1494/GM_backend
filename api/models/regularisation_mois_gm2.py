from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model()


class Regularisation_Mois_GM2(models.Model):
    code_regularisation = models.CharField(max_length=100, unique=True)
    montant_regularisation = models.DecimalField(max_digits=20, decimal_places=4)
    est_bloque = models.BooleanField(default=False)
    user_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,default=1
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code_regularisation
