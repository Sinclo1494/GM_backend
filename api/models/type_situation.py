from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model()

class Type_Situation(models.Model):
    code_type_situation = models.CharField(max_length=100)
    libelle_type_situation = models.CharField(max_length=100)
    est_bloque = models.BooleanField(default=False)
    code_type_affectation = models.ForeignKey(
        "Type_Affectation",
        on_delete=models.PROTECT,
        db_column="code_type_affectation",
        to_field="code_type_affectation",
        related_name="types_situation",
    )
    user_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,default=1
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="unique_affectation_situation",
                fields=["code_type_affectation","code_type_situation"],
            )
        ]


    def __str__(self):
        return  f"{self.code_type_affectation} - {self.code_type_situation}"