from django.db import models


class Filiale(models.Model):
    code_filiale = models.CharField(max_length=100, unique=True)
    code_entreprise = models.ForeignKey(
        "Entreprise",
        on_delete=models.PROTECT,
        db_column="code_entreprise",
        related_name="filiales",
    )
    libelle_filiale = models.CharField(max_length=100)
    est_bloque = models.BooleanField(default=False)
    user_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code_filiale
