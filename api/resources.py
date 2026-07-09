from import_export import resources, fields
from datetime import datetime
from import_export.widgets import ForeignKeyWidget, DateTimeWidget
from .models import (
    Marque_Materiel,
    Type_Marque,
    Famille_Materiel,
    Categorie_GM,
    Sous_Famille_Materiel,
    Entreprise,
    Filiale,
    Grand_Materiel,
    Site,
    Affectation_Materiel,
    Pointage,
    Type_Affectation,
    Type_Situation,
    Regularisation_GM,
)


DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y",
    "%Y-%m-%d",
)

def normalize_datetime(value):
    if not value:
        return None

    if not isinstance(value, str):
        return value

    value = value.strip()

    # SQL Server can export 7 fractional digits; Python accepts up to 6.
    if "." in value:
        date_part, frac = value.split(".", 1)
        if frac.isdigit():
            value = f"{date_part}.{frac[:6]}"

    for fmt in DATETIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass

    return value

# Type_Marque class resources
class Type_Marque_Resource(resources.ModelResource):
    code_marque = fields.Field(
        column_name="code_marque",
        attribute="code_marque",
        widget=ForeignKeyWidget(Marque_Materiel, "code_marque"),
    )

    class Meta:
        model = Type_Marque

        fields = (
            "code_type_marque",
            "libelle_type_marque",
            "code_marque",
            "est_bloque",
        )

        import_id_fields = ("code_type_marque",)
    

    def before_import_row(self, row, **kwargs):
        code = row.get("code_marque")

        if not code:
            # allow NULL FK
            row["code_marque"] = None
            return


# Famille_Materiel class resources
class Famille_Materiel_Resource(resources.ModelResource):
    code_categorie_gm = fields.Field(
        column_name="code_categorie_gm",
        attribute="code_categorie_gm",
        widget=ForeignKeyWidget(Categorie_GM, "code_categorie"),
    )

    class Meta:
        model = Famille_Materiel

        fields = (
            "code_famille",
            "code_categorie_gm",
            "liebelle_famille",
            "est_bloque",
        )

        import_id_fields = ("code_famille",)


# Sous_Famille_Materiel class resources
class Sous_Famille_Materiel_Resource(resources.ModelResource):
    code_famille_materiel = fields.Field(
        column_name="code_famille_materiel",
        attribute="code_famille_materiel",
        widget=ForeignKeyWidget(Famille_Materiel, "code_famille"),
    )

    class Meta:
        model = Sous_Famille_Materiel
        fields = (
            "code_sous_famille",
            "libelle_sous_famille",
            "code_famille_materiel",
            "est_bloque",
        )

        import_id_fields = ("code_sous_famille",)


# Filiale class resource


class Filiale_Resource(resources.ModelResource):
    code_entreprise = fields.Field(
        column_name="code_entreprise",
        attribute="code_entreprise",
        widget=ForeignKeyWidget(Entreprise, "code_entreprise"),
    )

    class Meta:
        model = Filiale
        fields = (
            "code_filiale",
            "code_entreprise",
            "libelle_filiale",
            "est_bloque",
        )
        import_id_fields = ("code_filiale",)


# grand_Materiel class resource
class Grand_Materiel_Resource(resources.ModelResource):
    code_sous_famille_materiel = fields.Field(
        column_name="code_sous_famille_materiel",
        attribute="code_sous_famille_materiel",
        widget=ForeignKeyWidget(Sous_Famille_Materiel, "code_sous_famille"),
    )

    code_type_marque = fields.Field(
        column_name="code_type_marque",
        attribute="code_type_marque",
        widget=ForeignKeyWidget(Type_Marque, "code_type_marque"),
    )

    code_filiale_g = fields.Field(
        column_name="code_filiale_g",
        attribute="code_filiale_g",
        widget=ForeignKeyWidget(Filiale, "code_filiale"),
    )

    class Meta:
        model = Grand_Materiel
        fields = (
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
            "code_filiale_g",
            "date_modification",
        )
        import_id_fields = ("code_materiel",)
    
    def before_import_row(self, row, **kwargs):
        row["date_modification"] = normalize_datetime(row.get("date_modification"))


# Site class resource
class Site_Resource(resources.ModelResource):
    code_filiale = fields.Field(
        column_name="code_filiale",
        attribute="code_filiale",
        widget=ForeignKeyWidget(Filiale, "code_filiale"),
    )

    class Meta:
        model = Site
        fields = (
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
        )
        import_id_fields = ("code_site",)


# Affectation_Materiel class resource
class Affectation_Materiel_Resource(resources.ModelResource):
    code_materiel = fields.Field(
        column_name="code_materiel",
        attribute="code_materiel",
        widget=ForeignKeyWidget(Grand_Materiel, "code_materiel"),
    )
    code_filiale_mere = fields.Field(
        column_name="code_filiale_mere",
        attribute="code_filiale_mere",
        widget=ForeignKeyWidget(Filiale, "code_filiale"),
    )
    code_site = fields.Field(
        column_name="code_site",
        attribute="code_site",
        widget=ForeignKeyWidget(Site, "code_site"),
    )
    date_affectation = fields.Field(
        column_name="date_affectation",
        attribute="date_affectation",
        widget=DateTimeWidget(format="%Y-%m-%d %H:%M:%S"),
    )
    date_debut_affectation = fields.Field(
        column_name="date_debut_affectation",
        attribute="date_debut_affectation",
        widget=DateTimeWidget(format="%Y-%m-%d %H:%M:%S"),
    )
    date_fin_affectation = fields.Field(
        column_name="date_fin_affectation",
        attribute="date_fin_affectation",
        widget=DateTimeWidget(format="%Y-%m-%d %H:%M:%S"),
    )

    class Meta:
        model = Affectation_Materiel
        fields = (
            "code_affectation",
            "code_materiel",
            "code_filiale_mere",
            "code_site",
            "date_affectation",
            "date_fin_affectation",
            "nbr_jours_affectation",
            "date_debut_affectation",
            "prenable",
            "est_bloque",
        )

        import_id_fields = ("code_affectation", "code_site")

    def before_import_row(self, row, **kwargs):
        row["date_affectation"] = normalize_datetime(row.get("date_affectation"))
        row["date_debut_affectation"] = normalize_datetime(row.get("date_debut_affectation"))
        row["date_fin_affectation"] = normalize_datetime(row.get("date_fin_affectation"))


# pointage class resource
class Pointage_Resource(resources.ModelResource):
    affectation_id = fields.Field(column_name="affectation_id", attribute="affectation_id")
    class Meta:
        model = Pointage
        fields = (
            "affectation_id",
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
            "date_modification",
            "est_bloque",
        )
        import_id_fields = ("mmaa",)
        
    def before_import(self, dataset, **kwargs):
        print("caching started ...")
        self.affectations = {
            (a.code_affectation, a.code_site.code_site): a
            for a in Affectation_Materiel.objects.select_related("code_site")
        }
        print("Caching finished successfully")

    def before_import_row(self, row, **kwargs):
        
        affectation = self.affectations.get(
            (row["code_affectation"], row["code_site"])
        )

        if not affectation:
            raise ValueError(
                f"Affectation not found for {row.get('code_affectation')} + {row.get('code_site')}"
            )
        
        row["affectation_id"]=affectation
        row["date_modification"] = normalize_datetime(row.get("date_modification"))

#Type situation class resource
class Type_Situation_Resource(resources.ModelResource):
    code_type_affectation = fields.Field(
        column_name="code_type_affectation",
        attribute="code_type_affectation",
        widget=ForeignKeyWidget(Type_Affectation,"code_type_affectation"),
    )
    
    class Meta:
        model = Type_Situation
        fields=(
            "code_type_situation",
            "libelle_type_situation",
            "code_type_affectation",
            "est_bloque",
        )
        import_id_fields=("code_type_situation","code_type_affectation",)

#Regularisation GM class resource
class Regularisation_GM_Resource(resources.ModelResource):
    code_site = fields.Field(
        column_name="code_site",
        attribute="code_site",
        widget=ForeignKeyWidget(Site, "code_site"),
    )
    mmaa=fields.Field(
        column_name="mmaa",
        attribute="mmaa",
    )
    
    class Meta:
        model = Regularisation_GM
        fields=(
            "code_site",
            "mmaa",
            "montant_regularisation",
            "est_bloque",
            "date_modification",
        )
        import_id_fields=("code_site","mmaa",)