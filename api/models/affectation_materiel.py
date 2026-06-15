from django.db import models

class Affectation_Materiel(models.Model):
    code_affectation = models.CharField(max_length=100, unique=True)
    code_materiel = models.ForeignKey(
        "Grand_Materiel",
        on_delete=models.PROTECT,
        db_column="code_materiel",
        related_name="affectations",
    )

    code_filiale_mere = models.ForeignKey(
        "Filiale",
        on_delete=models.PROTECT,
        db_column="code_filiale_mere",
        related_name="affectations",
    )

    code_site = models.ForeignKey(
        "Site",
        on_delete=models.PROTECT,
        db_column="code_site",
        related_name="affectations",
    )
    date_affectation = models.DateField()
    date_fin_affectation = models.DateField()
    nbr_jours_affectation = models.IntegerField()
    date_debut_affectation = models.DateField()
    prenable = models.BooleanField(default=False)
    est_bloque = models.BooleanField(default=False)
    user_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return self.code_affectation