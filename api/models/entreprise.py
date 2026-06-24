from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model()

class Entreprise(models.Model):
    code_entreprise = models.CharField(max_length=100, unique=True)
    raison_sociale = models.CharField(max_length=100)
    numero_identification_fiscale = models.CharField(max_length=100,null=True,blank=True)
    numero_article_imposition = models.CharField(max_length=100,null=True,blank=True)
    numero_registre_commerce = models.CharField(max_length=100)
    numero_compte_bancaire = models.CharField(max_length=100)
    capital_social = models.DecimalField(max_digits=25, decimal_places=4)
    entete = models.TextField(blank=True, null=True)
    date_registre_commerce = models.DateField()
    logo = models.ImageField(upload_to='logos/', blank=True, null=True)
    type_dossier = models.CharField(max_length=100)
    est_bloque = models.BooleanField(default=False)
    user_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,default=1
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code_entreprise