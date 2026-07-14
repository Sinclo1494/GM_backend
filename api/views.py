import json

from django.shortcuts import render
from django.http import JsonResponse

from rest_framework import status, viewsets
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .services.csv_import.pointage_schema import POINTAGE_SCHEMA
from .services.csv_import.validation_cache import ValidationCache
from .services.csv_import.csv_importer import (
    CsvImporter,
    ValidationExpiredError,
    PointageImportError,
)

from api.services import (
    PointageImportService,
    SituationImportService,
    AnalyseQuantitative,
    AnalyseQuantitativeResume,
    AnalyseExploitation,
    AnalyseExploitationResume,
    CsvValidator,
)






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


class GrandMaterielViewSet(viewsets.ModelViewSet):
    queryset = Grand_Materiel.objects.all()
    serializer_class = GrandMaterielSerializer


class MarqueMaterielViewSet(viewsets.ModelViewSet):
    queryset = Marque_Materiel.objects.all()
    serializer_class = MarqueMaterielSerializer


class TypeMarqueViewSet(viewsets.ModelViewSet):
    queryset = Type_Marque.objects.all()
    serializer_class = TypeMarqueSerializer


class SousFamilleMaterielViewSet(viewsets.ModelViewSet):
    queryset = Sous_Famille_Materiel.objects.all()
    serializer_class = SousFamilleMaterielSerializer


class FamilleMaterielViewSet(viewsets.ModelViewSet):
    queryset = Famille_Materiel.objects.all()
    serializer_class = FamilleMaterielSerializer

class CategorieGMViewSet(viewsets.ModelViewSet):
    queryset = Categorie_GM.objects.all()
    serializer_class = CategorieGMSerializer

class TypeAffectationViewSet(viewsets.ModelViewSet):
    queryset = Type_Affectation.objects.all()
    serializer_class = TypeAffectationSerializer

class TypeSituationViewSet(viewsets.ModelViewSet):
    queryset = Type_Situation.objects.all()
    serializer_class = TypeSituationSerializer

class TypeEtatMaterielViewSet(viewsets.ModelViewSet):
    queryset = Type_Etat_Materiel.objects.all()
    serializer_class = TypeEtatMaterielSerializer

class SituationMaterielViewSet(viewsets.ModelViewSet):
    queryset = Situation_Materiel.objects.all()
    serializer_class = SituationMaterielSerializer

class EntrepriseViewSet(viewsets.ModelViewSet):
    queryset = Entreprise.objects.all()
    serializer_class = EntrepriseSerializer

class FilialeViewSet(viewsets.ModelViewSet):
    queryset = Filiale.objects.all()
    serializer_class = FilialeSerializer

class AffectationMaterielViewSet(viewsets.ModelViewSet):
    queryset = Affectation_Materiel.objects.all()
    serializer_class = AffectationMaterielSerializer

class DivisionViewSet(viewsets.ModelViewSet):
    queryset = Division.objects.all()
    serializer_class = DivisionSerializer

class FamilleStructuresViewSet(viewsets.ModelViewSet):
    queryset = Famille_Structures.objects.all()
    serializer_class = FamilleStructuresSerializer

class PointageViewSet(viewsets.ModelViewSet):
    queryset = Pointage.objects.all()
    serializer_class = PointageSerializer

class RegularisationGMViewSet(viewsets.ModelViewSet):
    queryset = Regularisation_GM.objects.all()
    serializer_class = RegularisationGMSerializer

class RegularisationMoisGM2ViewSet(viewsets.ModelViewSet):
    queryset = Regularisation_Mois_GM2.objects.all()
    serializer_class = RegularisationMoisGM2Serializer

class SiteViewSet(viewsets.ModelViewSet):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer

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

            validator = CsvValidator(
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

            importer = CsvImporter(
                validation_id=validation_id,
            )

            result = importer.import_data()

        except ValidationExpiredError as exc:

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
