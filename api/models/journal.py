from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class JournalActions:
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    IMPORT = "IMPORT"

    CHOICES = [
        (CREATE, "Création"),
        (UPDATE, "Modification"),
        (DELETE, "Suppression"),
        (IMPORT, "Import"),
    ]


class JournalModules:
    MATERIEL = "MATERIEL"
    AFFECTATION = "AFFECTATION"
    SITUATION = "SITUATION"
    POINTAGE = "POINTAGE"
    REGULARISATION = "REGULARISATION"
    UTILISATEUR = "UTILISATEUR"
    ADMINISTRATION = "ADMINISTRATION"
    MARQUE = "MARQUE"
    TYPE_MARQUE = "TYPE_MARQUE"
    SOUS_FAMILLE = "SOUS_FAMILLE"
    SITE = "SITE"
    SITUATION_AFFECTATION = "SITUATION_AFFECTATION"
    FAMILLE = "FAMILLE"
    CATEGORIE = "CATEGORIE"
    TYPE_ETAT = "TYPE_ETAT"

    CHOICES = [
        (MATERIEL, "Matériel"),
        (AFFECTATION, "Affectation"),
        (SITUATION, "Situation"),
        (POINTAGE, "Pointage"),
        (REGULARISATION, "Régularisation"),
        (UTILISATEUR, "Utilisateur"),
        (ADMINISTRATION, "Administration"),
        (MARQUE, "Marque"),
        (TYPE_MARQUE, "Type de Marque"),
        (SOUS_FAMILLE, "Sous-Famille"),
        (SITE, "Site"),
        (SITUATION_AFFECTATION, "Situation Affectation"),
        (FAMILLE, "Famille"),
        (CATEGORIE, "Catégorie"),
        (TYPE_ETAT, "Type d'État"),
    ]


class Journal(models.Model):
    date_action = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_entries",
    )
    action = models.CharField(
        max_length=20,
        choices=JournalActions.CHOICES,
    )
    module = models.CharField(
        max_length=25,
        choices=JournalModules.CHOICES,
    )
    objet_type = models.CharField(max_length=100)
    objet_id = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    ancienne_valeur = models.JSONField(null=True, blank=True)
    nouvelle_valeur = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    code_filiale = models.CharField(max_length=100, null=True, blank=True)
    code_site = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "api"
        ordering = ["-date_action"]
        verbose_name = "Journal"
        verbose_name_plural = "Journaux"

    def __str__(self):
        return f"{self.date_action} — {self.user} — {self.module} — {self.action}"
