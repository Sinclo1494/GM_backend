from django.db import models


class Grand_Materiel(models.Model):
    code_materiel = models.CharField(max_length=100, unique=True)
    designation = models.CharField(max_length=100)
    num_serie = models.CharField(max_length=100)
    immatriculation = models.CharField(max_length=100)
    date_acquisition = models.DateField()
    valeur_acquisition = models.DecimalField(max_digits=10, decimal_places=2)
    valeur_remplacement = models.DecimalField(max_digits=10, decimal_places=2)
    taux_amortissement = models.DecimalField(max_digits=5, decimal_places=2)
    puissance_materiel = models.DecimalField(max_digits=10, decimal_places=2)
    code_sous_famille_materiel = models.ForeignKey(
        "Sous_Famille_Materiel",
        on_delete=models.PROTECT,
        db_column="code_sous_famille_materiel",
        related_name="grand_materiels",
    )
    code_type_marque = models.ForeignKey(
        "Type_Marque",
        on_delete=models.PROTECT,
        db_column="code_type_marque",
        related_name="grand_materiels",
    )
    est_bloque = models.BooleanField(default=False)
    user_id = models.IntegerField()
    code_filiale_g = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code_materiel
