from django.db import models


class Sous_Famille_Materiel(models.Model):
    code_sous_famille = models.CharField(max_length=100, unique=True)
    libelle_sous_famille = models.CharField(max_length=100)
    code_famille_materiel = models.ForeignKey(
        "Famille_Materiel",
        on_delete=models.PROTECT,
        db_column="code_famille",
        related_name="sous_familles",
    )
    est_bloque = models.BooleanField(default=False)
    user_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code_sous_famille
