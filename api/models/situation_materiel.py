from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model()


class Situation_Materiel(models.Model):
    id_situation = models.CharField(max_length=100, unique=True,null=True, blank=True)
    affectation_id = models.ForeignKey(
        "Affectation_Materiel",
        on_delete=models.PROTECT,
        to_field="id",
        db_column="affectation_id",
        related_name="situation_ids",
    )
    type_situation_id = models.ForeignKey(
        "Type_Situation",
        on_delete=models.PROTECT,
        db_column="type_situation_id",
        to_field="id",
        related_name="situation_ids",
    )
    code_type_etat_materiel = models.ForeignKey(
        "Type_Etat_Materiel",
        on_delete=models.PROTECT,
        db_column="code_type_etat_materiel",
        related_name="situations",
    )
    date_situation = models.DateTimeField()
    est_bloque = models.BooleanField(default=False)
    user_id = models.ForeignKey(User, on_delete=models.PROTECT, default=1)
    date_modification = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.id)
