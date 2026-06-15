from django.db import models

class Site(models.Model):
    code_site = models.CharField(max_length=100, unique=True)
    code_filiale = models.ForeignKey(
        "Filiale",
        on_delete=models.PROTECT,
        db_column="code_filiale",
        related_name="sites",
    )
    code_region = models.CharField(max_length=100)
    libelle_site = models.CharField(max_length = 100)
    code_agence = models.CharField(max_length = 100)
    type_site = models.CharField(max_length = 100)
    code_division = models.ForeignKey(
        "Division",
        on_delete=models.PROTECT,
        db_column="code_division",
        related_name="sites"
    )
    numero_ss_employeur = models.CharField(max_length=100)
    code_commune_site = models.CharField(max_length=100)
    jour_cloture_mouv_RH_paie = models.IntegerField()
    date_ouverture_site = models.DateField()
    date_cloture_site = models.DateField()
    est_bloque = models.BooleanField(default=False)
    user_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)