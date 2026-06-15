from django.contrib import admin
from .models import Grand_Materiel
from .models import Marque_Materiel
from .models import Type_Marque
from .models import Sous_Famille_Materiel
from .models import Famille_Materiel
from .models import Categorie_GM
from .models import Type_Affectation
from .models import Type_Situation
from .models import Type_Etat_Materiel
from .models import Situation_Materiel
from .models import Entreprise
from .models import Filiale
from .models import Affectation_Materiel
from .models import Division
from .models import Famille_Structures
from .models import Pointage
from .models import Regularisation_GM
from .models import Regularisation_Mois_GM2
from .models import Site

class GrandMaterielAdmin(admin.ModelAdmin):
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
        "created_at",
        "updated_at",
    )
    search_fields = ("code_materiel", "designation")
    list_filter = ("est_bloque", "date_acquisition")


class MarqueMaterielAdmin(admin.ModelAdmin):
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


class TypeMarqueAdmin(admin.ModelAdmin):
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


class SousFamilleMaterielAdmin(admin.ModelAdmin):
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

class FamilleMaterielAdmin(admin.ModelAdmin):
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

class CategorieGMAdmin(admin.ModelAdmin):
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

class TypeAffectationAdmin(admin.ModelAdmin):
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

class TypeSituationAdmin(admin.ModelAdmin):
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

class TypeEtatMaterielAdmin(admin.ModelAdmin):
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

class SituationMaterielAdmin(admin.ModelAdmin):
    list_display = (
        "code_situation",
        "libelle_situation",
        "est_bloque",
        "code_type_situation",
        "code_type_etat_materiel",
        "code_type_affectation",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_situation", "libelle_situation")
    list_filter = ("est_bloque",)

class EntrepriseAdmin(admin.ModelAdmin):
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

class FilialeAdmin(admin.ModelAdmin):
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

class AffectationMaterielAdmin(admin.ModelAdmin):
    list_display = (
        "code_affectation",
        "code_materiel",
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
    search_fields = ("code_affectation",)
    list_filter = ("est_bloque",)

class DivisionAdmin(admin.ModelAdmin):
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
    
class FamilleStructuresAdmin(admin.ModelAdmin):
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

class PointageAdmin(admin.ModelAdmin):
    list_display = (
        "code_pointage",
        "code_affectation",
        "code_site",
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
        "created_at",
        "updated_at",
    )
    search_fields = ("code_pointage",)
    list_filter = ("est_bloque",)

class RegularisationGMAdmin(admin.ModelAdmin):
    list_display = (
        "code_regularisation",
        "code_site",
        "montant_regularisation",
        "mmaa",
        "observation",
        "est_bloque",
        "user_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("code_regularisation",)
    list_filter = ("est_bloque",)

class RegularisationMoisGM2Admin(admin.ModelAdmin):
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

class SiteAdmin(admin.ModelAdmin):
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
        "jour_cloture_mouv_rh_paie",
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
#TODO : register admin site