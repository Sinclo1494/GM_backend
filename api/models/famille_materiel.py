from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model()

class Famille_Materiel(models.Model):
    code_famille = models.CharField(max_length=100, unique=True)
    code_categorie_gm = models.ForeignKey(
        "Categorie_GM",
        on_delete=models.PROTECT,
        db_column="code_categorie_gm",
        to_field="code_categorie",
        related_name="familles_materiel",
    )
    libelle_famille = models.CharField(max_length=100)
    est_bloque = models.BooleanField(default=False)
    user_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,default=1
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
#todo: add code_cateogorie_gm field 
    def __str__(self):
        return self.code_famille