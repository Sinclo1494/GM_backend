from django.shortcuts import render
from rest_framework import viewsets

import tablib
from django.http import JsonResponse
from api.services import PointageImportService,SituationImportService





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

