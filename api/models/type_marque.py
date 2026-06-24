from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model()


class Type_Marque(models.Model):
    code_type_marque = models.CharField(max_length=100, unique=True)
    libelle_type_marque = models.CharField(max_length=100)
    code_marque = models.ForeignKey(
        "Marque_Materiel",
        on_delete=models.PROTECT,
        db_column="code_marque",
        to_field="code_marque",
        related_name="types",
        null= True,
        blank=True
    )
    est_bloque = models.BooleanField(default=False)
    user_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,default=1
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code_type_marque



