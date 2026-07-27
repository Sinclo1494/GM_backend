from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model()

class Affectation_Materiel(models.Model):
    code_affectation = models.CharField(max_length=100)
    code_materiel = models.ForeignKey(
        "Grand_Materiel",
        on_delete=models.PROTECT,
        db_column="code_materiel",
        to_field="code_materiel",
        related_name="affectations",
    )

    code_filiale_mere = models.ForeignKey(
        "Filiale",
        on_delete=models.PROTECT,
        db_column="code_filiale_mere",
        to_field="code_filiale",
        related_name="affectations",
    )

    code_site = models.ForeignKey(
        "Site",
        on_delete=models.PROTECT,
        db_column="code_site",
        to_field="code_site",
        related_name="affectations",
    )
    date_affectation = models.DateTimeField()
    date_fin_affectation = models.DateTimeField(null=True,blank=True)
    nbr_jours_affectation = models.IntegerField(default=0)
    date_debut_affectation = models.DateTimeField(null=True,blank=True)
    prenable = models.BooleanField(default=False)
    est_bloque = models.BooleanField(default=False)
    user_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,default=1
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="unique_affectation_site",
                fields=["code_affectation","code_site"],
            )
        ]


    def __str__(self):
        return  f"{self.code_affectation} - {self.code_site}"