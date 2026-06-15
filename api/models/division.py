from django.db import models


class Division(models.Model):
    code_division = models.CharField(max_length=100, unique=True)
    libelle_division = models.CharField(max_length=100)
    code_filiale = models.ForeignKey(
        "Filiale",
        on_delete=models.PROTECT,
        db_column="code_filiale",
        related_name="divisions",
    )
    est_bloque = models.BooleanField(default=False)
    user_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code_division
