from django.db import models


class Type_Marque(models.Model):
    code_type_marque = models.CharField(max_length=100, unique=True)
    libelle_type_marque = models.CharField(max_length=100)
    code_marque = models.ForeignKey(
        "Marque_Materiel",
        on_delete=models.PROTECT,
        db_column="code_marque",
        related_name="types",
    )
    est_bloque = models.BooleanField(default=False)
    user_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code_type_marque


class Meta:
    db_table = "type_marque"
