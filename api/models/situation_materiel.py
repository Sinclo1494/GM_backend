from django.db import models


class Situation_Materiel(models.Model):
    code_situation = models.CharField(max_length=100, unique=True)
    libelle_situation = models.CharField(max_length=100)
    est_bloque = models.BooleanField(default=False)
    code_type_situation = models.ForeignKey(
        "Type_Situation",
        on_delete=models.PROTECT,
        db_column="code_type_situation",
        related_name="situations",
    )
    code_type_etat_materiel = models.ForeignKey(
        "Type_Etat_Materiel",
        on_delete=models.PROTECT,
        db_column="code_type_etat_materiel",
        related_name="situations",
    )
    code_type_affectation = models.ForeignKey(
        "Type_Affectation",
        on_delete=models.PROTECT,
        db_column="code_type_affectation",
        related_name="situations",
    )
    
    user_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code_situation
