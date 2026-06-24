from django.contrib import admin
from .models import (
    Grand_Materiel,
    Marque_Materiel,
    Type_Marque,
    Sous_Famille_Materiel,
    Famille_Materiel,
    Categorie_GM,
    Type_Affectation,
    Type_Situation,
    Type_Etat_Materiel,
    Situation_Materiel,
    Entreprise,
    Filiale,
    Affectation_Materiel,
    Division,
    Famille_Structures,
    Pointage,
    Regularisation_GM,
    Regularisation_Mois_GM2,
    Site,
)
from import_export.admin import ImportExportModelAdmin
from .resources import (
    Type_Marque_Resource,
    Famille_Materiel_Resource,
    Sous_Famille_Materiel_Resource,
    Filiale_Resource,
    Grand_Materiel_Resource,
    Site_Resource,
    Affectation_Materiel_Resource,
    Pointage_Resource,
    Type_Situation_Resource,
    Regularisation_GM_Resource)




class GrandMaterielAdmin(ImportExportModelAdmin):
    resource_class=Grand_Materiel_Resource
    list_display = (
        "code_materiel",
        "designation",
        "num_serie",
        "immatriculation",
        "date_acquisition",
        "valeur_acquisition",
        "valeur_remplacement",
        "taux_amortissement",
        "puissance_materiel",
        "code_sous_famille_materiel",
        "code_type_marque",
        "est_bloque",
        "user_id",
        "code_filiale_g",
        "date_modification",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_materiel", "designation")
    list_filter = ("est_bloque", "date_acquisition")


class MarqueMaterielAdmin(ImportExportModelAdmin):
    list_display = (
        "code_marque",
        "libelle_marque",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_marque", "libelle_marque")
    list_filter = ("est_bloque",)


class TypeMarqueAdmin(ImportExportModelAdmin):
    resource_class = Type_Marque_Resource
    list_display = (
        "code_type_marque",
        "libelle_type_marque",
        "code_marque",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_type_marque", "libelle_type_marque")
    list_filter = ("est_bloque",)


class SousFamilleMaterielAdmin(ImportExportModelAdmin):
    resource_class=Sous_Famille_Materiel_Resource
    list_display = (
        "code_sous_famille",
        "libelle_sous_famille",
        "code_famille_materiel",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_sous_famille", "libelle_sous_famille")
    list_filter = ("est_bloque",)

class FamilleMaterielAdmin(ImportExportModelAdmin):
    resource_class = Famille_Materiel_Resource
    list_display = (
        "code_famille",
        "libelle_famille",
        "code_categorie_gm",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_famille", "libelle_famille")
    list_filter = ("est_bloque",)

class CategorieGMAdmin(ImportExportModelAdmin):
    list_display = (
        "code_categorie",
        "libelle_categorie",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_categorie", "libelle_categorie")
    list_filter = ("est_bloque",)

class TypeAffectationAdmin(ImportExportModelAdmin):
    list_display = (
        "code_type_affectation",
        "libelle_type_affectation",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_type_affectation", "libelle_type_affectation")
    list_filter = ("est_bloque",)

class TypeSituationAdmin(ImportExportModelAdmin):
    resource_class=Type_Situation_Resource
    list_display = (
        "code_type_situation",
        "libelle_type_situation",
        "code_type_affectation",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_type_situation", "libelle_type_situation")
    list_filter = ("est_bloque",)

class TypeEtatMaterielAdmin(ImportExportModelAdmin):
    list_display = (
        "code_type_etat_materiel",
        "libelle_type_etat_materiel",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_type_etat_materiel", "libelle_type_etat_materiel")
    list_filter = ("est_bloque",)

class SituationMaterielAdmin(ImportExportModelAdmin):
    list_display = (
        "id_situation",
        "type_situation_id",
        "code_type_etat_materiel",
        "affectation_id",
        "date_situation",
        "date_modification",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("id_situation",)
    list_filter = ("est_bloque",)

class EntrepriseAdmin(ImportExportModelAdmin):
    list_display = (
        "code_entreprise",
        "raison_sociale",
        "numero_identification_fiscale",
        "numero_article_imposition",
        "numero_registre_commerce",
        "numero_compte_bancaire",
        "capital_social",
        "entete",
        "date_registre_commerce",
        "logo",
        "type_dossier",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_entreprise", "raison_sociale")
    list_filter = ("est_bloque",)

class FilialeAdmin(ImportExportModelAdmin):
    resource_class= Filiale_Resource
    list_display = (
        "code_filiale",
        "libelle_filiale",
        "est_bloque",
        "code_entreprise",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_filiale", "libelle_filiale")
    list_filter = ("est_bloque",)

class AffectationMaterielAdmin(ImportExportModelAdmin):
    resource_class = Affectation_Materiel_Resource
    list_display = (
        "id",
        "code_affectation",
        "code_materiel",
        "code_site",
        "code_filiale_mere",
        "date_affectation",
        "date_fin_affectation",
        "nbr_jours_affectation",
        "date_debut_affectation",
        "prenable",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_affectation","code_site__code_site")
    list_filter = ("est_bloque",)

class DivisionAdmin(ImportExportModelAdmin):
    list_display = (
        "code_division",
        "libelle_division",
        "code_filiale",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_division", "libelle_division")
    list_filter = ("est_bloque",)
    
class FamilleStructuresAdmin(ImportExportModelAdmin):
    list_display = (
        "code_famille_structure",
        "libelle_famille_structure",
        "numero_ordre",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_famille_structure", "libelle_famille_structure")
    list_filter = ("est_bloque",)

class PointageAdmin(ImportExportModelAdmin):
    resource_class= Pointage_Resource
    list_display = (
        "affectation_id",
        "mmaa",
        "taux_location",
        "heures_service",
        "heures_chomage",
        "heures_panne",
        "potentiel",
        "montant_service",
        "montant_chomage",
        "montant_panne",
        "est_bloque",
        "user_id",
        "date_modification",
        "created_at",
        "updated_at",
    )
    search_fields = ("affectation_id__code_affectation","mmaa")
    list_filter = ("est_bloque",)

class RegularisationGMAdmin(ImportExportModelAdmin):
    resource_class=Regularisation_GM_Resource
    list_display = (
        "code_site",
        "montant_regularisation",
        "mmaa",
        "observation",
        "est_bloque",
        "user_id",
        "date_modification",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_site__code_site","mmaa",)
    list_filter = ("est_bloque",)

class RegularisationMoisGM2Admin(ImportExportModelAdmin):
    list_display = (
        "code_regularisation",
        "montant_regularisation",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_regularisation",)
    list_filter = ("est_bloque",)

class SiteAdmin(ImportExportModelAdmin):
    resource_class=Site_Resource
    list_display = (
        "code_site",
        "code_filiale",
        "code_region",
        "libelle_site",
        "code_agence",
        "type_site",
        "code_division",
        "numero_ss_employeur",
        "code_commune_site",
        "jour_cloture_mouv_RH_paie",
        "date_ouverture_site",
        "date_cloture_site",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_site", "libelle_site")
    list_filter = ("est_bloque",)






admin.site.register(Grand_Materiel, GrandMaterielAdmin)
admin.site.register(Marque_Materiel, MarqueMaterielAdmin)
admin.site.register(Type_Marque, TypeMarqueAdmin)
admin.site.register(Sous_Famille_Materiel, SousFamilleMaterielAdmin)
admin.site.register(Famille_Materiel, FamilleMaterielAdmin)
admin.site.register(Categorie_GM, CategorieGMAdmin)
admin.site.register(Type_Affectation, TypeAffectationAdmin)
admin.site.register(Type_Situation, TypeSituationAdmin)
admin.site.register(Type_Etat_Materiel, TypeEtatMaterielAdmin)
admin.site.register(Situation_Materiel, SituationMaterielAdmin)
admin.site.register(Filiale, FilialeAdmin)
admin.site.register(Entreprise, EntrepriseAdmin)
admin.site.register(Affectation_Materiel, AffectationMaterielAdmin)
admin.site.register(Division, DivisionAdmin)
admin.site.register(Famille_Structures, FamilleStructuresAdmin)
admin.site.register(Pointage, PointageAdmin)
admin.site.register(Regularisation_GM, RegularisationGMAdmin)
admin.site.register(Regularisation_Mois_GM2, RegularisationMoisGM2Admin)
admin.site.register(Site, SiteAdmin)