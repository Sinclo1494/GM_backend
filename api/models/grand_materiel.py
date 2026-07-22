from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model()


class Grand_Materiel(models.Model):
    code_materiel = models.CharField(max_length=100, unique=True)
    designation = models.CharField(max_length=100)
    num_serie = models.CharField(max_length=100, null=True, blank=True)
    immatriculation = models.CharField(max_length=100, null=True, blank=True)
    date_acquisition = models.DateField(null=True,blank=True)
    valeur_acquisition = models.DecimalField(max_digits=20, decimal_places=6)
    valeur_remplacement = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    taux_amortissement = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    puissance_materiel = models.CharField(max_length=100, null=True, blank=True)
    code_sous_famille_materiel = models.ForeignKey(
        "Sous_Famille_Materiel",
        on_delete=models.PROTECT,
        db_column="code_sous_famille_materiel",
        to_field="code_sous_famille",
        related_name="grand_materiels",
    )
    code_type_marque = models.ForeignKey(
        "Type_Marque",
        on_delete=models.PROTECT,
        db_column="code_type_marque",
        to_field="code_type_marque",
        related_name="grand_materiels",
        null=True,
        blank=True
    )
    est_bloque = models.BooleanField(default=False)
    user_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,default=1
    )
    code_filiale_g = models.ForeignKey(
        "Filiale",
        on_delete=models.PROTECT,
        db_column="code_filiale_g",
        to_field="code_filiale",
        related_name="filiales",
    )
    date_modification = models.DateTimeField(null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code_materiel
