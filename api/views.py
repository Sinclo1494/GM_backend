import json

from django.shortcuts import render
from django.http import JsonResponse

from rest_framework import status, viewsets, permissions, mixins
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import OrderingFilter
from django.db.models import F, Value, CharField
from django.db.models.functions import Concat

from .services.journal_service import (
    log_action,
    log_csv_import,
    serialize_for_journal,
)
from .models.journal import JournalActions, JournalModules

from .services.pointage_csv_import.pointage_schema import POINTAGE_SCHEMA
from .services.gm_csv_import.gm_schema import GRAND_MATERIEL_SCHEMA
from .services.marque_csv_import.marque_schema import MARQUE_MATERIEL_SCHEMA
from .services.type_marque_csv_import.type_marque_schema import TYPE_MARQUE_SCHEMA
from .services.sous_famille_csv_import.sous_famille_schema import SOUS_FAMILLE_SCHEMA
from .services.situation_affectation_csv_import.situation_affectation_schema import SITUATION_AFFECTATION_SCHEMA
from .services.site_csv_import.site_schema import SITE_SCHEMA
from .services.regularisation_csv_import.regularisation_schema import REGULARISATION_GM_SCHEMA
from .services.validation_cache import ValidationCache
from .services.pointage_csv_import.csv_importer import (
    PointageCsvImporter,
    PointageValidationExpiredError,
    PointageImportError,
)
from .services.gm_csv_import.csv_importer import (
    GMCsvImporter,
    GMValidationExpiredError,
    GrandMaterielImportError
)

from .services.marque_csv_import.csv_importer import (
    MarqueCsvImporter,
    MarqueValidationExpiredError,
    MarqueImportError
)

from .services.type_marque_csv_import.csv_importer import (
    TypeMarqueCsvImporter,
    TypeMarqueValidationExpiredError,
    TypeMarqueImportError
)

from .services.sous_famille_csv_import.csv_importer import (
    SousFamilleCsvImporter,
    SousFamilleValidationExpiredError,
    SousFamilleImportError
)

from .services.situation_affectation_csv_import.csv_importer import (
    SituationAffectationCsvImporter,
    SituationAffectationValidationExpiredError,
    SituationAffectationImportError
)

from .services.site_csv_import.csv_importer import (
    SiteCsvImporter,
    SiteValidationExpiredError,
    SiteImportError
)

from .services.regularisation_csv_import.csv_importer import (
    RegularisationGMCsvImporter,
    RegularisationGMValidationExpiredError,
    RegularisationGMImportError
)

from api.services import (
    PointageImportService,
    SituationImportService,
    AnalyseQuantitative,
    AnalyseQuantitativeResume,
    AnalyseExploitation,
    AnalyseExploitationResume,
    PointageCsvValidator,
    GMCsvValidator,
    MarqueCsvValidator,
    TypeMarqueCsvValidator,
    SousFamilleCsvValidator,
    SituationAffectationCsvValidator,
    SiteCsvValidator,
    RegularisationGMCsvValidator,
)
from api.services.dashboard_service import DashboardService






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


from .serializers import GrandMaterielSerializer
from .serializers import MarqueMaterielSerializer
from .serializers import TypeMarqueSerializer
from .serializers import SousFamilleMaterielSerializer
from .serializers import FamilleMaterielSerializer
from .serializers import CategorieGMSerializer
from .serializers import TypeAffectationSerializer
from .serializers import TypeSituationSerializer
from .serializers import TypeEtatMaterielSerializer
from .serializers import SituationMaterielSerializer
from .serializers import EntrepriseSerializer
from .serializers import FilialeSerializer
from .serializers import AffectationMaterielSerializer
from .serializers import DivisionSerializer
from .serializers import FamilleStructuresSerializer
from .serializers import PointageSerializer
from .serializers import RegularisationGMSerializer
from .serializers import RegularisationMoisGM2Serializer
from .serializers import SiteSerializer
from .serializers import JournalSerializer
from .filters import (
    AffectationMaterielFilter,
    SituationMaterielFilter,
    GrandMaterielFilter,
    PointageFilter,
)


# ---------------------------------------------------------
# JournalisedModelViewSet mixin
# ---------------------------------------------------------

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 1000

class SearchableModelViewSet(viewsets.ModelViewSet):
    search_fields = []
    pagination_class = StandardResultsSetPagination
    filter_backends = []
    ordering_fields = []
    ordering = []

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        if search and self.search_fields:
            from django.db.models import Q
            q = Q()
            for field in self.search_fields:
                q |= Q(**{f"{field}__icontains": search})
            qs = qs.filter(q)
        return qs

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs.setdefault("context", self.get_serializer_context())
        return serializer_class(*args, **kwargs)


class JournalisedModelViewSet(SearchableModelViewSet):
    """
    ModelViewSet that records journal (audit) entries for
    CREATE, UPDATE, and DELETE operations.

    Subclasses must set:
      - journal_module   (JournalModules value)
      - journal_objet_type (string, typically the model class name)
      - journal_filiale_field  (FK attr name for code_filiale, optional)
      - journal_site_field  (FK attr name for code_site, optional)
    """

    journal_module = None
    journal_objet_type = None
    journal_filiale_field = None
    journal_site_field = None

    def _get_filiale_code(self, instance):
        if self.journal_filiale_field:
            fk = getattr(instance, self.journal_filiale_field, None)
            if fk is not None:
                return getattr(fk, "code_filiale", None)
        return None

    def _get_site_code(self, instance):
        if self.journal_site_field:
            fk = getattr(instance, self.journal_site_field, None)
            if fk is not None:
                return getattr(fk, "code_site", None)
        return None

    def _serialize_instance(self, instance):
        serializer = self.get_serializer(instance)
        data = dict(serializer.data)
        for key, value in list(data.items()):
            if value is not None and hasattr(value, "isoformat"):
                data[key] = value.isoformat()
        return data

    def perform_create(self, serializer):
        instance = serializer.save()
        log_action(
            user=self.request.user,
            action=JournalActions.CREATE,
            module=self.journal_module,
            objet_type=self.journal_objet_type,
            objet_id=instance.pk,
            nouvelle_valeur=self._serialize_instance(instance),
            request=self.request,
            code_filiale=self._get_filiale_code(instance),
            code_site=self._get_site_code(instance),
            description=f"Création de {self.journal_objet_type}",
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        old_data = self._serialize_instance(instance)

        super().perform_update(serializer)

        new_data = self._serialize_instance(instance)

        log_action(
            user=self.request.user,
            action=JournalActions.UPDATE,
            module=self.journal_module,
            objet_type=self.journal_objet_type,
            objet_id=instance.pk,
            ancienne_valeur=old_data,
            nouvelle_valeur=new_data,
            request=self.request,
            code_filiale=self._get_filiale_code(instance),
            code_site=self._get_site_code(instance),
            description=f"Modification de {self.journal_objet_type}",
        )

    def perform_destroy(self, instance):
        old_data = self._serialize_instance(instance)
        filiale = self._get_filiale_code(instance)
        site = self._get_site_code(instance)
        pk = instance.pk
        objet_type = self.journal_objet_type
        module = self.journal_module

        super().perform_destroy(instance)

        log_action(
            user=self.request.user,
            action=JournalActions.DELETE,
            module=module,
            objet_type=objet_type,
            objet_id=pk,
            ancienne_valeur=old_data,
            request=self.request,
            code_filiale=filiale,
            code_site=site,
            description=f"Suppression de {objet_type}",
        )


# ---------------------------------------------------------
# Journal ViewSet (read-only, immutable)
# ---------------------------------------------------------

class JournalViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Journal.objects.all()
    serializer_class = JournalSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["description", "objet_type", "objet_id"]

    def get_queryset(self):
        qs = super().get_queryset()

        date_debut = self.request.query_params.get("date_debut")
        if date_debut:
            qs = qs.filter(date_action__gte=date_debut)

        date_fin = self.request.query_params.get("date_fin")
        if date_fin:
            qs = qs.filter(date_action__date__lte=date_fin)

        username = self.request.query_params.get("user")
        if username:
            qs = qs.filter(user__username__icontains=username)

        module = self.request.query_params.get("module")
        if module:
            qs = qs.filter(module=module)

        action = self.request.query_params.get("action")
        if action:
            qs = qs.filter(action=action)

        objet_id = self.request.query_params.get("objet_id")
        if objet_id:
            qs = qs.filter(objet_id=objet_id)

        code_filiale = self.request.query_params.get("code_filiale")
        if code_filiale:
            qs = qs.filter(code_filiale=code_filiale)

        code_site = self.request.query_params.get("code_site")
        if code_site:
            qs = qs.filter(code_site=code_site)

        search = self.request.query_params.get("search")
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(description__icontains=search)
                | Q(objet_type__icontains=search)
                | Q(objet_id__icontains=search)
            )

        return qs


class GrandMaterielViewSet(JournalisedModelViewSet):
    queryset = Grand_Materiel.objects.all().select_related(
        "code_sous_famille_materiel",
        "code_type_marque",
        "code_filiale_g",
        "user_id",
    )
    serializer_class = GrandMaterielSerializer
    journal_module = JournalModules.MATERIEL
    journal_objet_type = "Grand_Materiel"
    journal_filiale_field = "code_filiale_g"
    search_fields = ["code_materiel", "designation", "num_serie", "immatriculation"]
    filter_backends = [OrderingFilter, GrandMaterielFilter]
    ordering_fields = [
        "code_materiel", "designation", "num_serie", "immatriculation",
        "code_filiale_g", "code_sous_famille_materiel", "code_type_marque",
        "date_acquisition", "valeur_acquisition", "valeur_remplacement",
        "taux_amortissement", "puissance_materiel", "est_bloque",
    ]
    ordering = ["code_materiel"]


class MarqueMaterielViewSet(JournalisedModelViewSet):
    queryset = Marque_Materiel.objects.all()
    serializer_class = MarqueMaterielSerializer
    journal_module = JournalModules.MARQUE
    journal_objet_type = "Marque_Materiel"
    search_fields = ["code_marque", "libelle_marque"]


class TypeMarqueViewSet(JournalisedModelViewSet):
    queryset = Type_Marque.objects.all()
    serializer_class = TypeMarqueSerializer
    journal_module = JournalModules.TYPE_MARQUE
    journal_objet_type = "Type_Marque"
    search_fields = ["code_type_marque", "libelle_type_marque"]


class SousFamilleMaterielViewSet(JournalisedModelViewSet):
    queryset = Sous_Famille_Materiel.objects.all()
    serializer_class = SousFamilleMaterielSerializer
    journal_module = JournalModules.SOUS_FAMILLE
    journal_objet_type = "Sous_Famille_Materiel"
    search_fields = ["code_sous_famille", "libelle_sous_famille"]


class FamilleMaterielViewSet(JournalisedModelViewSet):
    queryset = Famille_Materiel.objects.all()
    serializer_class = FamilleMaterielSerializer
    journal_module = JournalModules.MARQUE
    journal_objet_type = "Famille_Materiel"
    search_fields = ["code_famille", "libelle_famille"]

class CategorieGMViewSet(JournalisedModelViewSet):
    queryset = Categorie_GM.objects.all()
    serializer_class = CategorieGMSerializer
    journal_module = JournalModules.MARQUE
    journal_objet_type = "Categorie_GM"
    search_fields = ["code_categorie", "libelle_categorie"]

class TypeAffectationViewSet(JournalisedModelViewSet):
    queryset = Type_Affectation.objects.all()
    serializer_class = TypeAffectationSerializer
    journal_module = JournalModules.AFFECTATION
    journal_objet_type = "Type_Affectation"
    search_fields = ["code_type_affectation", "libelle_type_affectation"]

class TypeSituationViewSet(JournalisedModelViewSet):
    queryset = Type_Situation.objects.all()
    serializer_class = TypeSituationSerializer
    journal_module = JournalModules.SITUATION
    journal_objet_type = "Type_Situation"
    search_fields = ["code_type_situation", "libelle_type_situation"]

class TypeEtatMaterielViewSet(JournalisedModelViewSet):
    queryset = Type_Etat_Materiel.objects.all()
    serializer_class = TypeEtatMaterielSerializer
    journal_module = JournalModules.SITUATION
    journal_objet_type = "Type_Etat_Materiel"
    search_fields = ["code_type_etat_materiel", "libelle_type_etat_materiel"]

class SituationMaterielViewSet(JournalisedModelViewSet):
    queryset = Situation_Materiel.objects.all().select_related(
        "affectation_id",
        "affectation_id__code_materiel",
        "affectation_id__code_filiale_mere",
        "affectation_id__code_site",
        "type_situation_id",
        "type_situation_id__code_type_affectation",
        "code_type_etat_materiel",
        "user_id",
    )
    serializer_class = SituationMaterielSerializer
    journal_module = JournalModules.SITUATION
    journal_objet_type = "Situation_Materiel"
    search_fields = ["id_situation", "affectation_id__code_materiel__code_materiel"]
    filter_backends = [OrderingFilter, SituationMaterielFilter]
    ordering_fields = ["date_situation", "id_situation", "est_bloque"]
    ordering = ["-date_situation"]

class EntrepriseViewSet(JournalisedModelViewSet):
    queryset = Entreprise.objects.all()
    serializer_class = EntrepriseSerializer
    journal_module = JournalModules.ADMINISTRATION
    journal_objet_type = "Entreprise"
    search_fields = ["code_entreprise", "raison_sociale"]

class FilialeViewSet(JournalisedModelViewSet):
    queryset = Filiale.objects.all()
    serializer_class = FilialeSerializer
    journal_module = JournalModules.ADMINISTRATION
    journal_objet_type = "Filiale"
    search_fields = ["code_filiale", "libelle_filiale"]

class AffectationMaterielViewSet(JournalisedModelViewSet):
    queryset = Affectation_Materiel.objects.all().select_related(
        "code_materiel",
        "code_filiale_mere",
        "code_site",
        "user_id",
    )
    serializer_class = AffectationMaterielSerializer
    journal_module = JournalModules.AFFECTATION
    journal_objet_type = "Affectation_Materiel"
    journal_filiale_field = "code_filiale_mere"
    journal_site_field = "code_site"
    search_fields = ["code_affectation", "code_materiel__code_materiel", "code_site__code_site"]
    filter_backends = [OrderingFilter, AffectationMaterielFilter]
    ordering_fields = ["code_affectation", "date_affectation", "est_bloque", "prenable"]
    ordering = ["-date_affectation"]

class DivisionViewSet(JournalisedModelViewSet):
    queryset = Division.objects.all()
    serializer_class = DivisionSerializer
    journal_module = JournalModules.ADMINISTRATION
    journal_objet_type = "Division"
    search_fields = ["code_division", "libelle_division"]

class FamilleStructuresViewSet(JournalisedModelViewSet):
    queryset = Famille_Structures.objects.all()
    serializer_class = FamilleStructuresSerializer
    journal_module = JournalModules.ADMINISTRATION
    journal_objet_type = "Famille_Structures"
    search_fields = ["code_famille_structure", "libelle_famille_structure"]

class PointageViewSet(JournalisedModelViewSet):
    queryset = Pointage.objects.all().select_related(
        "affectation_id",
        "affectation_id__code_materiel",
        "affectation_id__code_filiale_mere",
        "affectation_id__code_site",
        "user_id",
    )
    serializer_class = PointageSerializer
    journal_module = JournalModules.POINTAGE
    journal_objet_type = "Pointage"
    search_fields = ["affectation_id__code_affectation", "mmaa"]
    filter_backends = [OrderingFilter, PointageFilter]
    ordering_fields = ["mmaa", "date_modification", "est_bloque"]
    ordering = ["-mmaa", "-date_modification"]

class RegularisationGMViewSet(JournalisedModelViewSet):
    queryset = Regularisation_GM.objects.all()
    serializer_class = RegularisationGMSerializer
    journal_module = JournalModules.REGULARISATION
    journal_objet_type = "Regularisation_GM"
    journal_site_field = "code_site"
    search_fields = ["code_site__code_site", "mmaa"]


class RegularisationMoisGM2ViewSet(JournalisedModelViewSet):
    queryset = Regularisation_Mois_GM2.objects.all()
    serializer_class = RegularisationMoisGM2Serializer
    journal_module = JournalModules.REGULARISATION
    journal_objet_type = "Regularisation_Mois_GM2"
    search_fields = ["code_regularisation"]

class SiteViewSet(JournalisedModelViewSet):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    journal_module = JournalModules.SITE
    journal_objet_type = "Site"
    journal_filiale_field = "code_filiale"
    search_fields = ["code_site", "libelle_site", "code_region"]

def pointage_upload_view(request):
    #this used to import csv pointage data from db (features bulk import to make it faster)
    if request.method == "POST":

        file_obj = request.FILES["file"]
        service = PointageImportService(file_obj)
        service.import_data()
 
        return JsonResponse({
            "success": True,
            "message": "Import completed successfully"
        })

    return render(request, "pointage_upload.html")

def situation_upload_view(request):

    if request.method == "POST":

        file_obj = request.FILES["file"]
        service = SituationImportService(file_obj)
        service.import_data()
 
        return JsonResponse({
            "success": True,
            "message": "Import completed successfully"
        })

    return render(request, "situation_upload.html")

class TP_AQ_API_View(APIView):
    def get(self, request):
        code_filiale = request.query_params.get("code_filiale")
        date_debut = request.query_params.get("date_debut")
        date_fin = request.query_params.get("date_fin")

        data = AnalyseQuantitative.get_situations(
            code_filiale=code_filiale,
            date_debut=date_debut,
            date_fin=date_fin,
        )

        return Response(data)

class TP_AQ_resume_API_View(APIView):
    def get(self, request):
        code_filiale = request.query_params.get("code_filiale")
        date_debut = request.query_params.get("date_debut")
        date_fin = request.query_params.get("date_fin")

        data = AnalyseQuantitativeResume.get_situations_resume(
            code_filiale=code_filiale,
            date_debut=date_debut,
            date_fin=date_fin,
        )

        return Response(data)

class TP_AE_API_View(APIView):
    def get(self, request):
        code_filiale = request.query_params.get("code_filiale")
        date_debut = request.query_params.get("date_debut")
        date_fin = request.query_params.get("date_fin")

        data = AnalyseExploitation.get_pointages(
            code_filiale=code_filiale,
            date_debut=date_debut,
            date_fin=date_fin,
        )

        return Response(data)

class TP_AE_resume_API_View(APIView):
    def get(self, request):
        code_filiale = request.query_params.get("code_filiale")
        date_debut = request.query_params.get("date_debut")
        date_fin = request.query_params.get("date_fin")

        data = AnalyseExploitationResume.get_pointages_resume(
            code_filiale=code_filiale,
            date_debut=date_debut,
            date_fin=date_fin,
        )

        return Response(data)


class DashboardMaterialDetailsAPIView(APIView):
    """
    GET /api/dashboard/material-details/
    Query params:
      code_filiale (optional)
      date_debut (optional)
      date_fin (optional)
      code_famille (optional)
      search (optional)
      page (optional, default 1)
      page_size (optional, default 50)
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        code_filiale = request.query_params.get("code_filiale")
        date_debut = request.query_params.get("date_debut")
        date_fin = request.query_params.get("date_fin")
        code_famille = request.query_params.get("code_famille")
        search = request.query_params.get("search")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 50))

        qs = Grand_Materiel.objects.filter(est_bloque=False).select_related(
            "code_sous_famille_materiel",
            "code_sous_famille_materiel__code_famille_materiel",
            "code_type_marque",
            "code_filiale_g",
        )

        if code_filiale:
            qs = qs.filter(code_filiale_g=code_filiale)

        if code_famille:
            qs = qs.filter(code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille)

        if search:
            qs = qs.filter(
                Q(code_materiel__icontains=search)
                | Q(designation__icontains=search)
                | Q(code_type_marque__code_type_marque__icontains=search)
            )

        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        items = qs[start:end]

        result = []
        for gm in items:
            sous_famille = gm.code_sous_famille_materiel
            famille = sous_famille.code_famille_materiel if sous_famille else None

            result.append({
                "code_materiel": gm.code_materiel,
                "designation": gm.designation,
                "code_sous_famille": sous_famille.code_sous_famille if sous_famille else "",
                "libelle_sous_famille": sous_famille.libelle_sous_famille if sous_famille else "",
                "code_famille": famille.code_famille if famille else "",
                "libelle_famille": famille.libelle_famille if famille else "",
                "code_type_marque": gm.code_type_marque.code_type_marque if gm.code_type_marque else "",
                "libelle_type_marque": gm.code_type_marque.libelle_type_marque if gm.code_type_marque else "",
                "code_filiale": gm.code_filiale_g.code_filiale if gm.code_filiale_g else "",
                "libelle_filiale": gm.code_filiale_g.libelle_filiale if gm.code_filiale_g else "",
                "est_bloque": gm.est_bloque,
            })

        return Response({
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size,
        })

class ValidatePointageView(APIView):

    parser_classes = [MultiPartParser]

    def post(self, request):

        # -----------------------------------------------------
        # 1. File
        # -----------------------------------------------------

        file = request.FILES.get("file")

        if file is None:
            return Response(
                {
                    "success": False,
                    "message": "Aucun fichier reçu.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 2. Filiale
        # -----------------------------------------------------

        filiale = request.POST.get("filiale")

        if not filiale or not filiale.strip():
            return Response(
                {
                    "success": False,
                    "message": "La filiale est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        filiale = filiale.strip()

        # -----------------------------------------------------
        # 3. Mapping
        # -----------------------------------------------------

        raw_mapping = request.POST.get("mapping")

        if not raw_mapping:
            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            mapping = json.loads(raw_mapping)

        except (json.JSONDecodeError, TypeError):
            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(mapping, dict):
            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 4. Validation
        # -----------------------------------------------------

        try:

            validator = PointageCsvValidator(
                uploaded_file=file,
                schema=POINTAGE_SCHEMA,
                mapping=mapping,
                filiale=filiale,
            )

            report = validator.validate()

        except Exception as exc:
            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 5. Serialize validation result
        # -----------------------------------------------------

        response_data = report.to_dict()

        # -----------------------------------------------------
        # 6. Cache only successful validations
        # -----------------------------------------------------

        if report.success:

            validation_id = ValidationCache.save(
                report=report,
                filiale=filiale,
                filename=file.name,
            )

            response_data["validation_id"] = validation_id

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )


class ImportPointageView(APIView):

    parser_classes = [JSONParser]

    def post(self, request):

        # -----------------------------------------------------
        # 1. Validation ID
        # -----------------------------------------------------

        validation_id = request.data.get("validation_id")

        if not validation_id:
            return Response(
                {
                    "success": False,
                    "message": "L'identifiant de validation est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 2. Import already validated rows
        # -----------------------------------------------------

        try:

            importer = PointageCsvImporter(
                validation_id=validation_id,
            )

            result = importer.import_data()

            try:
                log_csv_import(
                    request,
                    result,
                    JournalModules.POINTAGE,
                )
            except Exception:
                pass

        except PointageValidationExpiredError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_410_GONE,
            )

        except PointageImportError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except Exception:

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue "
                        "pendant l'import."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -----------------------------------------------------
        # 3. Successful import
        # -----------------------------------------------------

        return Response(
            {
                **result,
                "message": "Import terminé avec succès.",
            },
            status=status.HTTP_201_CREATED,
        )


class ValidateGrandMaterielView(APIView):

    parser_classes = [MultiPartParser]

    def post(self, request):

        # -----------------------------------------------------
        # 1. Uploaded file
        # -----------------------------------------------------

        file = request.FILES.get("file")

        if file is None:

            return Response(
                {
                    "success": False,
                    "message": "Aucun fichier reçu.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 2. Selected filiale
        #
        # The UI filiale is optional if the CSV already
        # contains the code_filiale_g column.
        # -----------------------------------------------------

        filiale = request.POST.get("filiale")

        if filiale:
            filiale = filiale.strip()

        # -----------------------------------------------------
        # 3. Column mapping
        # -----------------------------------------------------

        raw_mapping = request.POST.get("mapping")

        if not raw_mapping:

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            mapping = json.loads(raw_mapping)

        except (json.JSONDecodeError, TypeError):

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(mapping, dict):

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 4. Validate CSV
        # -----------------------------------------------------

        try:

            validator = GMCsvValidator(
                uploaded_file=file,
                schema=GRAND_MATERIEL_SCHEMA,
                mapping=mapping,
                filiale=filiale,
            )

            report = validator.validate()

        except Exception as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 5. Build response
        # -----------------------------------------------------

        response_data = report.to_dict()

        # -----------------------------------------------------
        # 6. Cache successful validation
        # -----------------------------------------------------

        if report.success:

            validation_id = ValidationCache.save(
                report=report,
                filiale=filiale,
                filename=file.name,
            )

            response_data["validation_id"] = validation_id

        # -----------------------------------------------------
        # 7. Return validation result
        # -----------------------------------------------------

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )
    
class ImportGrandMaterielView(APIView):

    parser_classes = [JSONParser]

    def post(self, request):

        # -----------------------------------------------------
        # 1. Validation ID
        # -----------------------------------------------------

        validation_id = request.data.get("validation_id")

        if not validation_id:

            return Response(
                {
                    "success": False,
                    "message": "L'identifiant de validation est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 2. Import validated rows
        # -----------------------------------------------------

        try:

            importer = GMCsvImporter(
                validation_id=validation_id,
            )

            result = importer.import_data()

            try:
                log_csv_import(
                    request,
                    result,
                    JournalModules.MATERIEL,
                )
            except Exception:
                pass

        except GMValidationExpiredError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_410_GONE,
            )

        except GrandMaterielImportError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except Exception:

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue "
                        "pendant l'import."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -----------------------------------------------------
        # 3. Successful import
        # -----------------------------------------------------

        return Response(
            {
                **result,
                "message": "Import terminé avec succès.",
            },
            status=status.HTTP_201_CREATED,
        )
    

class ValidateMarqueView(APIView):

    parser_classes = [MultiPartParser]

    def post(self, request):

        # -----------------------------------------------------
        # 1. Uploaded file
        # -----------------------------------------------------

        file = request.FILES.get("file")

        if file is None:

            return Response(
                {
                    "success": False,
                    "message": "Aucun fichier reçu.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


        # -----------------------------------------------------
        # 2. Column mapping
        # -----------------------------------------------------

        raw_mapping = request.POST.get("mapping")

        if not raw_mapping:

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            mapping = json.loads(raw_mapping)

        except (json.JSONDecodeError, TypeError):

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(mapping, dict):

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 3. Validate CSV
        # -----------------------------------------------------

        try:

            validator = MarqueCsvValidator(
                uploaded_file=file,
                schema=MARQUE_MATERIEL_SCHEMA,
                mapping=mapping,
            )

            report = validator.validate()

        except Exception as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 4. Build response
        # -----------------------------------------------------

        response_data = report.to_dict()

        # -----------------------------------------------------
        # 5. Cache successful validation
        # -----------------------------------------------------

        if report.success:

            validation_id = ValidationCache.save(
                report=report,
                filiale='',
                filename=file.name,
            )

            response_data["validation_id"] = validation_id

        # -----------------------------------------------------
        # 6. Return validation result
        # -----------------------------------------------------

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )
    
class ImportMarqueView(APIView):

    parser_classes = [JSONParser]

    def post(self, request):

        # -----------------------------------------------------
        # 1. Validation ID
        # -----------------------------------------------------

        validation_id = request.data.get("validation_id")

        if not validation_id:

            return Response(
                {
                    "success": False,
                    "message": "L'identifiant de validation est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 2. Import validated rows
        # -----------------------------------------------------

        try:

            importer = MarqueCsvImporter(
                validation_id=validation_id,
            )

            result = importer.import_data()

            try:
                log_csv_import(
                    request,
                    result,
                    JournalModules.MARQUE,
                )
            except Exception:
                pass

        except MarqueValidationExpiredError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_410_GONE,
            )

        except MarqueImportError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except Exception:

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue "
                        "pendant l'import."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -----------------------------------------------------
        # 3. Successful import
        # -----------------------------------------------------

        return Response(
            {
                **result,
                "message": "Import terminé avec succès.",
            },
            status=status.HTTP_201_CREATED,
        )
    
class ValidateTypeMarqueView(APIView):

    parser_classes = [MultiPartParser]

    def post(self, request):
        print ("this seems okay")

        # -----------------------------------------------------
        # 1. Uploaded file
        # -----------------------------------------------------

        file = request.FILES.get("file")

        if file is None:

            return Response(
                {
                    "success": False,
                    "message": "Aucun fichier reçu.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


        # -----------------------------------------------------
        # 2. Column mapping
        # -----------------------------------------------------

        raw_mapping = request.POST.get("mapping")

        if not raw_mapping:

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            mapping = json.loads(raw_mapping)

        except (json.JSONDecodeError, TypeError):

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(mapping, dict):

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 3. Validate CSV
        # -----------------------------------------------------

        try:

            validator = TypeMarqueCsvValidator(
                uploaded_file=file,
                schema=TYPE_MARQUE_SCHEMA,
                mapping=mapping,
            )

            report = validator.validate()

        except Exception as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 4. Build response
        # -----------------------------------------------------

        response_data = report.to_dict()

        # -----------------------------------------------------
        # 5. Cache successful validation
        # -----------------------------------------------------

        if report.success:

            validation_id = ValidationCache.save(
                report=report,
                filiale='',
                filename=file.name,
            )

            response_data["validation_id"] = validation_id

        # -----------------------------------------------------
        # 6. Return validation result
        # -----------------------------------------------------

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )

class ImportTypeMarqueView(APIView):

    parser_classes = [JSONParser]

    def post(self, request):

        # -----------------------------------------------------
        # 1. Validation ID
        # -----------------------------------------------------

        validation_id = request.data.get("validation_id")

        if not validation_id:

            return Response(
                {
                    "success": False,
                    "message": "L'identifiant de validation est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 2. Import validated rows
        # -----------------------------------------------------

        try:

            importer = TypeMarqueCsvImporter(
                validation_id=validation_id,
            )

            result = importer.import_data()

            try:
                log_csv_import(
                    request,
                    result,
                    JournalModules.TYPE_MARQUE,
                )
            except Exception:
                pass

        except TypeMarqueValidationExpiredError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_410_GONE,
            )

        except TypeMarqueImportError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except Exception:

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue "
                        "pendant l'import."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -----------------------------------------------------
        # 3. Successful import
        # -----------------------------------------------------

        return Response(
            {
                **result,
                "message": "Import terminé avec succès.",
            },
            status=status.HTTP_201_CREATED,
        )
    
class ValidateSousFamilleView(APIView):

    parser_classes = [MultiPartParser]

    def post(self, request):
        print ("this seems okay")

        # -----------------------------------------------------
        # 1. Uploaded file
        # -----------------------------------------------------

        file = request.FILES.get("file")

        if file is None:

            return Response(
                {
                    "success": False,
                    "message": "Aucun fichier reçu.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


        # -----------------------------------------------------
        # 2. Column mapping
        # -----------------------------------------------------

        raw_mapping = request.POST.get("mapping")

        if not raw_mapping:

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            mapping = json.loads(raw_mapping)

        except (json.JSONDecodeError, TypeError):

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(mapping, dict):

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 3. Validate CSV
        # -----------------------------------------------------

        try:

            validator = SousFamilleCsvValidator(
                uploaded_file=file,
                schema=SOUS_FAMILLE_SCHEMA,
                mapping=mapping,
            )

            report = validator.validate()

        except Exception as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 4. Build response
        # -----------------------------------------------------

        response_data = report.to_dict()

        # -----------------------------------------------------
        # 5. Cache successful validation
        # -----------------------------------------------------

        if report.success:

            validation_id = ValidationCache.save(
                report=report,
                filiale='',
                filename=file.name,
            )

            response_data["validation_id"] = validation_id

        # -----------------------------------------------------
        # 6. Return validation result
        # -----------------------------------------------------

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )

class ImportSousFamilleView(APIView):

    parser_classes = [JSONParser]

    def post(self, request):

        # -----------------------------------------------------
        # 1. Validation ID
        # -----------------------------------------------------

        validation_id = request.data.get("validation_id")

        if not validation_id:

            return Response(
                {
                    "success": False,
                    "message": "L'identifiant de validation est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 2. Import validated rows
        # -----------------------------------------------------

        try:

            importer = SousFamilleCsvImporter(
                validation_id=validation_id,
            )

            result = importer.import_data()

            try:
                log_csv_import(
                    request,
                    result,
                    JournalModules.SOUS_FAMILLE,
                )
            except Exception:
                pass

        except SousFamilleValidationExpiredError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_410_GONE,
            )

        except SousFamilleImportError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except Exception:

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue "
                        "pendant l'import."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -----------------------------------------------------
        # 3. Successful import
        # -----------------------------------------------------

        return Response(
            {
                **result,
                "message": "Import terminé avec succès.",
            },
            status=status.HTTP_201_CREATED,
        )


class ValidateSituationAffectationView(APIView):

    parser_classes = [MultiPartParser]

    def post(self, request):

        # -----------------------------------------------------
        # 1. Uploaded file
        # -----------------------------------------------------

        file = request.FILES.get("file")

        if file is None:

            return Response(
                {
                    "success": False,
                    "message": "Aucun fichier reçu.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 2. Filiale
        # -----------------------------------------------------

        filiale = request.POST.get("filiale")

        if not filiale:

            return Response(
                {
                    "success": False,
                    "message": "La filiale est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 3. Column mapping
        # -----------------------------------------------------

        raw_mapping = request.POST.get("mapping")

        if not raw_mapping:

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            mapping = json.loads(raw_mapping)

        except (json.JSONDecodeError, TypeError):

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(mapping, dict):

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 4. Validate CSV
        # -----------------------------------------------------

        try:

            validator = SituationAffectationCsvValidator(
                uploaded_file=file,
                schema=SITUATION_AFFECTATION_SCHEMA,
                mapping=mapping,
                filiale=filiale,
            )

            report = validator.validate()

        except Exception as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 5. Build response
        # -----------------------------------------------------

        response_data = report.to_dict()

        # -----------------------------------------------------
        # 6. Cache successful validation
        # -----------------------------------------------------

        if report.success:

            validation_id = ValidationCache.save(
                report=report,
                filiale=filiale,
                filename=file.name,
            )

            response_data["validation_id"] = validation_id

        # -----------------------------------------------------
        # 7. Return validation result
        # -----------------------------------------------------

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )


class ImportSituationAffectationView(APIView):

    parser_classes = [JSONParser]

    def post(self, request):

        # -----------------------------------------------------
        # 1. Validation ID
        # -----------------------------------------------------

        validation_id = request.data.get("validation_id")

        if not validation_id:

            return Response(
                {
                    "success": False,
                    "message": "L'identifiant de validation est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


        # -----------------------------------------------------
        # 3. Import validated rows
        # -----------------------------------------------------

        try:

            importer = SituationAffectationCsvImporter(
                validation_id=validation_id,
            )

            result = importer.import_data()

            try:
                log_csv_import(
                    request,
                    result,
                    JournalModules.SITUATION_AFFECTATION,
                )
            except Exception:
                pass

        except SituationAffectationValidationExpiredError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_410_GONE,
            )

        except SituationAffectationImportError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except Exception:

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue "
                        "pendant l'import."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -----------------------------------------------------
        # 3. Successful import
        # -----------------------------------------------------

        return Response(
            {
                **result,
                "message": "Import terminé avec succès.",
            },
            status=status.HTTP_201_CREATED,
        )


class ValidateRegularisationGMView(APIView):

    parser_classes = [MultiPartParser]

    def post(self, request):

        file = request.FILES.get("file")

        if file is None:

            return Response(
                {
                    "success": False,
                    "message": "Aucun fichier reçu.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        filiale = request.POST.get("filiale")

        if filiale:
            filiale = filiale.strip()

        raw_mapping = request.POST.get("mapping")

        if not raw_mapping:

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            mapping = json.loads(raw_mapping)

        except (json.JSONDecodeError, TypeError):

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(mapping, dict):

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validator = RegularisationGMCsvValidator(
                uploaded_file=file,
                schema=REGULARISATION_GM_SCHEMA,
                mapping=mapping,
                filiale=filiale,
            )

            report = validator.validate()

        except Exception as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = report.to_dict()

        if report.success:

            validation_id = ValidationCache.save(
                report=report,
                filiale=filiale,
                filename=file.name,
            )

            response_data["validation_id"] = validation_id

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )


class ImportRegularisationGMView(APIView):

    parser_classes = [JSONParser]

    def post(self, request):

        validation_id = request.data.get("validation_id")

        if not validation_id:

            return Response(
                {
                    "success": False,
                    "message": "L'identifiant de validation est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            importer = RegularisationGMCsvImporter(
                validation_id=validation_id,
            )

            result = importer.import_data()

            try:
                log_csv_import(
                    request,
                    result,
                    JournalModules.REGULARISATION,
                )
            except Exception:
                pass

        except RegularisationGMValidationExpiredError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_410_GONE,
            )

        except RegularisationGMImportError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except Exception:

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue "
                        "pendant l'import."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                **result,
                "message": "Import terminé avec succès.",
            },
            status=status.HTTP_201_CREATED,
        )

class ValidateSiteView(APIView):

    parser_classes = [MultiPartParser]

    def post(self, request):

        # -----------------------------------------------------
        # 1. Uploaded file
        # -----------------------------------------------------

        file = request.FILES.get("file")

        if file is None:

            return Response(
                {
                    "success": False,
                    "message": "Aucun fichier reçu.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 2. Column mapping
        # -----------------------------------------------------

        raw_mapping = request.POST.get("mapping")

        if not raw_mapping:

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            mapping = json.loads(raw_mapping)

        except (json.JSONDecodeError, TypeError):

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(mapping, dict):

            return Response(
                {
                    "success": False,
                    "message": "Le mapping des colonnes est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 3. Validate CSV
        # -----------------------------------------------------

        try:

            validator = SiteCsvValidator(
                uploaded_file=file,
                schema=SITE_SCHEMA,
                mapping=mapping,
            )

            report = validator.validate()

        except Exception as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 4. Build response
        # -----------------------------------------------------

        response_data = report.to_dict()

        # -----------------------------------------------------
        # 5. Cache successful validation
        # -----------------------------------------------------

        if report.success:

            validation_id = ValidationCache.save(
                report=report,
                filiale="",
                filename=file.name,
            )

            response_data["validation_id"] = validation_id

        # -----------------------------------------------------
        # 6. Return validation result
        # -----------------------------------------------------

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )

class ImportSiteView(APIView):

    parser_classes = [JSONParser]

    def post(self, request):

        # -----------------------------------------------------
        # 1. Validation ID
        # -----------------------------------------------------

        validation_id = request.data.get("validation_id")

        if not validation_id:

            return Response(
                {
                    "success": False,
                    "message": "L'identifiant de validation est obligatoire.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 2. Import validated rows
        # -----------------------------------------------------

        try:

            importer = SiteCsvImporter(
                validation_id=validation_id,
            )

            result = importer.import_data()

            try:
                log_csv_import(
                    request,
                    result,
                    JournalModules.SITE,
                )
            except Exception:
                pass

        except SiteValidationExpiredError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_410_GONE,
            )

        except SiteImportError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except Exception:

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue "
                        "pendant l'import."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -----------------------------------------------------
        # 3. Successful import
        # -----------------------------------------------------

        return Response(
            {
                **result,
                "message": "Import terminé avec succès.",
            },
            status=status.HTTP_201_CREATED,
        )



class DashboardAPIView(APIView):
    """
    GET /api/dashboard/
    Query params:
      code_filiale (optional): filter by subsidiary code
      date_debut (optional, YYYY-MM-DD): start of period for pointage/regularisation
      date_fin (optional, YYYY-MM-DD): end of period for pointage/regularisation
      code_famille (optional): filter by material family code
      periode (optional): period label
      mode (optional): 'standard' or 'vs_cible'
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        code_filiale = request.query_params.get("code_filiale")
        date_debut = request.query_params.get("date_debut")
        date_fin = request.query_params.get("date_fin")
        code_famille = request.query_params.get("code_famille")
        periode = request.query_params.get("periode")
        mode = request.query_params.get("mode", "standard")
        niveau = request.query_params.get("niveau", "engin")

        data = DashboardService.get_dashboard(
            code_filiale=code_filiale,
            date_debut=date_debut,
            date_fin=date_fin,
            code_famille=code_famille,
            periode=periode,
            mode=mode,
            niveau=niveau,
        )

        return Response(data)
