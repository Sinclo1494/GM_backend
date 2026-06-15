from django.db import models


class Marque_Materiel(models.Model):
    code_marque = models.CharField(max_length=100, unique=True)
    libelle_marque = models.CharField(max_length=100)
    est_bloque = models.BooleanField(default=False)
    user_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code_marque
