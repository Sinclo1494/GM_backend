from rest_framework import serializers
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
from .models import Journal


class JournalSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    def get_user(self, obj):
        if obj.user:
            return {"id": obj.user.id, "username": obj.user.username}
        return None

    class Meta:
        model = Journal
        fields = "__all__"


class GrandMaterielSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grand_Materiel
        fields = "__all__"


class MarqueMaterielSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marque_Materiel
        fields = "__all__"


class TypeMarqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Type_Marque
        fields = "__all__"


class SousFamilleMaterielSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sous_Famille_Materiel
        fields = "__all__"


class FamilleMaterielSerializer(serializers.ModelSerializer):
    class Meta:
        model = Famille_Materiel
        fields = "__all__"


class CategorieGMSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categorie_GM
        fields = "__all__"


class TypeAffectationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Type_Affectation
        fields = "__all__"


class TypeSituationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Type_Situation
        fields = "__all__"


class TypeEtatMaterielSerializer(serializers.ModelSerializer):
    class Meta:
        model = Type_Etat_Materiel
        fields = "__all__"


class SituationMaterielSerializer(serializers.ModelSerializer):
    code_affectation = serializers.CharField(
        source="affectation_id.code_affectation", read_only=True
    )
    code_type_affectation = serializers.CharField(
        source="type_situation_id.code_type_affectation", read_only=True
    )
    code_type_situation = serializers.CharField(
        source="type_situation_id.code_type_situation", read_only=True
    )
    etat_materiel = serializers.CharField(
        source="code_type_etat_materiel.code_type_etat_materiel", read_only=True
    )
    filiale = serializers.CharField(
        source="affectation_id.code_filiale_mere", read_only=True
    )
    site = serializers.CharField(source="affectation_id.code_site", read_only=True)

    class Meta:
        model = Situation_Materiel
        fields = "__all__"


class EntrepriseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Entreprise
        fields = "__all__"


class FilialeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Filiale
        fields = "__all__"


class AffectationMaterielSerializer(serializers.ModelSerializer):
    class Meta:
        model = Affectation_Materiel
        fields = "__all__"


class DivisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Division
        fields = "__all__"


class FamilleStructuresSerializer(serializers.ModelSerializer):
    class Meta:
        model = Famille_Structures
        fields = "__all__"


class PointageSerializer(serializers.ModelSerializer):
    code_affectation = serializers.CharField(
        source="affectation_id.code_affectation", read_only=True
    )
    code_materiel = serializers.CharField(
        source="affectation_id.code_materiel.code_materiel", read_only=True
    )

    class Meta:
        model = Pointage
        fields = "__all__"


class RegularisationGMSerializer(serializers.ModelSerializer):
    class Meta:
        model = Regularisation_GM
        fields = "__all__"


class RegularisationMoisGM2Serializer(serializers.ModelSerializer):
    class Meta:
        model = Regularisation_Mois_GM2
        fields = "__all__"


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = "__all__"
