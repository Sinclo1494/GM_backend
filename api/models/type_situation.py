from django.db import models

class Type_Situation(models.Model):
    code_type_situation = models.CharField(max_length=100, unique=True)
    libelle_type_situation = models.CharField(max_length=100)
    est_bloque = models.BooleanField(default=False)
    code_type_affectation = models.ForeignKey(
        "Type_Affectation",
        on_delete=models.PROTECT,
        db_column="code_type_affectation",
        related_name="types_situation",
    )
    user_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code_type_situation