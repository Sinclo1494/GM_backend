from django.db import models

class Famille_Materiel(models.Model):
    code_famille = models.CharField(max_length=100, unique=True)
    code_categorie_gm = models.ForeignKey(
        "Categorie_GM",
        on_delete=models.PROTECT,
        db_column="code_categorie",
        related_name="familles_materiel",
    )
    libelle_famille = models.CharField(max_length=100)
    est_bloque = models.BooleanField(default=False)
    user_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
#todo: add code_cateogorie_gm field 
    def __str__(self):
        return self.code_famille