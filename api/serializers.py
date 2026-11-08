from .models import Notification
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Journal
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
from .models import UserProfile
from .models import ExternalServiceClient

User = get_user_model()



class JournalSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    def get_user(self, obj):
        if obj.user:
            return {"id": obj.user.id, "username": obj.user.username}
        return None

    class Meta:
        model = Journal
        fields = "__all__"


class ExternalServiceClientSerializer(serializers.ModelSerializer):
    allowed_filiales_codes = serializers.SerializerMethodField()
    created_by_username = serializers.SerializerMethodField()

    class Meta:
        model = ExternalServiceClient
        fields = [
            "id",
            "name",
            "client_id",
            "client_secret_hash",
            "is_active",
            "created_at",
            "updated_at",
            "expires_at",
            "last_used_at",
            "created_by",
            "created_by_username",
            "allowed_filiales",
            "allowed_filiales_codes",
        ]
        read_only_fields = ["id", "client_secret_hash", "created_at", "updated_at", "last_used_at", "created_by"]

    def get_allowed_filiales_codes(self, obj):
        return list(obj.allowed_filiales.values_list("code_filiale", flat=True))

    def get_created_by_username(self, obj):
        return obj.created_by.username if obj.created_by else None


class ExternalServiceClientWriteSerializer(serializers.ModelSerializer):
    client_secret = serializers.CharField(write_only=True, required=True, allow_blank=False)
    allowed_filiales_codes = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )

    class Meta:
        model = ExternalServiceClient
        fields = [
            "name",
            "client_id",
            "client_secret",
            "is_active",
            "expires_at",
            "allowed_filiales_codes",
        ]

    def create(self, validated_data):
        from api.services.external_service_credentials import hash_secret

        client_secret = validated_data.pop("client_secret", None)
        allowed_filiales_codes = validated_data.pop("allowed_filiales_codes", None)

        validated_data["client_secret_hash"] = hash_secret(client_secret)
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user

        instance = super().create(validated_data)

        if allowed_filiales_codes:
            from api.models import Filiale

            filiales = Filiale.objects.filter(code_filiale__in=allowed_filiales_codes)
            instance.allowed_filiales.set(filiales)

        self.context["client_secret"] = client_secret
        return instance

    def update(self, instance, validated_data):
        from api.services.external_service_credentials import hash_secret

        client_secret = validated_data.pop("client_secret", None)
        allowed_filiales_codes = validated_data.pop("allowed_filiales_codes", None)

        if client_secret:
            validated_data["client_secret_hash"] = hash_secret(client_secret)
            self.context["client_secret"] = client_secret

        instance = super().update(instance, validated_data)

        if allowed_filiales_codes is not None:
            from api.models import Filiale

            filiales = Filiale.objects.filter(code_filiale__in=allowed_filiales_codes)
            instance.allowed_filiales.set(filiales)

        return instance


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
    libelle_famille = serializers.CharField(
        source="code_sous_famille_materiel.code_famille_materiel.libelle_famille",
        read_only=True,
        default=None,
        allow_null=True,
    )
    libelle_categorie = serializers.CharField(
        source="code_sous_famille_materiel.code_famille_materiel.code_categorie_gm.libelle_categorie",
        read_only=True,
        default=None,
        allow_null=True,
    )
    libelle_marque = serializers.CharField(
        source="code_type_marque.code_marque.libelle_marque",
        read_only=True,
        default=None,
        allow_null=True,
    )
    libelle_filiale = serializers.CharField(
        source="code_filiale_g.libelle_filiale",
        read_only=True,
        default=None,
        allow_null=True,
    )
    libelle_sous_famille = serializers.CharField(
        source="code_sous_famille_materiel.libelle_sous_famille",
        read_only=True,
        default=None,
        allow_null=True,
    )
    libelle_type_marque = serializers.CharField(
        source="code_type_marque.libelle_type_marque",
        read_only=True,
        default=None,
        allow_null=True,
    )
    libelle_site = serializers.CharField(read_only=True, default=None, allow_null=True)

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
    code_site = serializers.CharField(
        source="affectation_id.code_site.code_site", read_only=True
    )
    code_filiale = serializers.CharField(
        source="affectation_id.code_filiale_mere.code_filiale", read_only=True
    )
    user = serializers.CharField(
        source="user_id.username", read_only=True, default=None
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


class UserSerializer(serializers.ModelSerializer):
    is_superuser = serializers.BooleanField(read_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    permissions = serializers.SerializerMethodField()
    filiale = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
            "is_superuser",
            "date_joined",
            "password",
            "permissions",
            "filiale",
        ]

    def get_permissions(self, obj):
        profile = getattr(obj, "profile", None)
        return list(profile.permissions) if profile else []

    def get_filiale(self, obj):
        profile = getattr(obj, "profile", None)
        if profile is None or profile.filiale is None:
            return None
        return profile.filiale.code_filiale


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["permissions"]


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["default_landing_page", "remember_last_visited_page", "last_visited_page"]


class CurrentUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    is_active = serializers.BooleanField()
    is_superuser = serializers.BooleanField()
    permissions = serializers.ListField(child=serializers.CharField())
    can_access_all_filiales = serializers.BooleanField(default=False)

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = "__all__"
