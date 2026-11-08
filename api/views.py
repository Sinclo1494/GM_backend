import json

import logging


from django.shortcuts import render
from django.db.models import Q


from django.http import JsonResponse


from rest_framework import status, viewsets, permissions, mixins


from rest_framework.decorators import action


from rest_framework.parsers import MultiPartParser, JSONParser


from rest_framework.response import Response


from rest_framework.views import APIView


from rest_framework.pagination import PageNumberPagination


from rest_framework.filters import OrderingFilter


from api.permissions import PagePermissionRequiredMixin, can_access_filiale, get_allowed_filiale_codes, resolve_filiale_code, can_access_all_filiales, can_include_pending_data


from django.conf import settings
from django.db import transaction


from django.db.models import F, Value, CharField, Count


from django.db.models.functions import Concat


from django.contrib.auth import get_user_model


from django.contrib.auth.password_validation import validate_password


from django.utils import timezone

from api.services.mgt_dashboard_service import MgtDashboardService
from .multidb import filiale_db_name, affiliate_routing

User = get_user_model()


# Module level logger: used by the generic error handlers so that no
# exception is ever swallowed without leaving a trace in the logs.
# Named "views_logger" because several methods assign a local "logger",
# which would shadow a module level "logger" for the whole function.
views_logger = logging.getLogger(__name__)


from .services.journal_service import (
    log_action,
    log_csv_import,
    serialize_for_journal,
)


from .models.journal import Journal, JournalActions, JournalModules


from .services.pointage_csv_import.pointage_schema import POINTAGE_SCHEMA


from .services.gm_csv_import.gm_schema import GRAND_MATERIEL_SCHEMA


from .services.marque_csv_import.marque_schema import MARQUE_MATERIEL_SCHEMA


from .services.type_marque_csv_import.type_marque_schema import TYPE_MARQUE_SCHEMA


from .services.sous_famille_csv_import.sous_famille_schema import SOUS_FAMILLE_SCHEMA


from .services.famille_csv_import.famille_schema import FAMILLE_SCHEMA


from .services.categorie_gm_csv_import.categorie_gm_schema import CATEGORIE_GM_SCHEMA


from .services.situation_affectation_csv_import.situation_affectation_schema import (
    SITUATION_AFFECTATION_SCHEMA,
)


from .services.site_csv_import.site_schema import SITE_SCHEMA


from .services.regularisation_csv_import.regularisation_schema import (
    REGULARISATION_GM_SCHEMA,
)


from .services.validation_cache import ValidationCache


from .services.pointage_csv_import.csv_importer import (
    PointageCsvImporter,
    PointageValidationExpiredError,
    PointageImportError,
)


from .services.gm_csv_import.csv_importer import (
    GMCsvImporter,
    GMValidationExpiredError,
    GrandMaterielImportError,
)


from .services.marque_csv_import.csv_importer import (
    MarqueCsvImporter,
    MarqueValidationExpiredError,
    MarqueImportError,
)


from .services.type_marque_csv_import.csv_importer import (
    TypeMarqueCsvImporter,
    TypeMarqueValidationExpiredError,
    TypeMarqueImportError,
)


from .services.sous_famille_csv_import.csv_importer import (
    SousFamilleCsvImporter,
    SousFamilleValidationExpiredError,
    SousFamilleImportError,
)


from .services.famille_csv_import.csv_importer import (
    FamilleCsvImporter,
    FamilleValidationExpiredError,
    FamilleImportError,
)


from .services.categorie_gm_csv_import.csv_importer import (
    CategorieGMCsvImporter,
    CategorieGMValidationExpiredError,
    CategorieGMImportError,
)


from .services.situation_affectation_csv_import.csv_importer import (
    SituationAffectationCsvImporter,
    SituationAffectationValidationExpiredError,
    SituationAffectationImportError,
)


from .services.site_csv_import.csv_importer import (
    SiteCsvImporter,
    SiteValidationExpiredError,
    SiteImportError,
)


from .services.regularisation_csv_import.csv_importer import (
    RegularisationGMCsvImporter,
    RegularisationGMValidationExpiredError,
    RegularisationGMImportError,
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
    FamilleCsvValidator,
    CategorieGMCsvValidator,
    SituationAffectationCsvValidator,
    SiteCsvValidator,
    RegularisationGMCsvValidator,
)


from api.services.dashboard_service import DashboardService
from api.services.dashboard_v2_service import DashboardV2Service


from .filters import GrandMaterielFilter, GrandMaterielOrderingFilter, MarqueMaterielFilter, TypeMarqueFilter, SousFamilleMaterielFilter, FamilleMaterielFilter, CategorieGMFilter, TypeAffectationFilter, TypeSituationFilter, TypeEtatMaterielFilter, SituationMaterielFilter, EntrepriseFilter, FilialeFilter, AffectationMaterielFilter, DivisionFilter, FamilleStructuresFilter, PointageFilter, PointageOrderingFilter, RegularisationGMFilter, RegularisationMoisGM2Filter, SiteFilter
from . import serializers
from .serializers import ExternalServiceClientSerializer, ExternalServiceClientWriteSerializer
from .models import ExternalServiceClient, Filiale, UserProfile
from .serializers import *
class StandardResultsSetPagination(PageNumberPagination):

    page_size = 50

    page_size_query_param = "page_size"

    max_page_size = 1000


class SearchableModelViewSet(PagePermissionRequiredMixin, viewsets.ModelViewSet):

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
            description=f"CrÃÂ©ation de {self.journal_objet_type}",
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
    PagePermissionRequiredMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):

    queryset = Journal.objects.all()

    serializer_class = JournalSerializer

    permission_required = "administration.journalisation"

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

    def get_queryset(self):
        return Grand_Materiel.objects.all().select_related(
            "code_sous_famille_materiel", "code_type_marque", "user_id", "code_filiale_g"
        )

    def list(self, request, *args, **kwargs):
        code_filiale = (
            request.query_params.get("filiale")
            or request.query_params.get("code_filiale")
            or request.query_params.get("libelle_filiale")
        )

        # Also check libelle_filiale to scope to a specific filiale if possible
        if not code_filiale and can_access_all_filiales(request.user):
            libelle_filiale_filter = request.query_params.get("libelle_filiale")
            if libelle_filiale_filter:
                from api.models import Filiale
                try:
                    f = Filiale.objects.filter(
                        Q(code_filiale__icontains=libelle_filiale_filter) | Q(libelle_filiale__icontains=libelle_filiale_filter)
                    ).first()
                    if f:
                        code_filiale = f.code_filiale
                except Exception:
                    pass

        # If a specific filiale is requested (and user can access it), route to that filiale DB
        if code_filiale and can_access_filiale(request.user, code_filiale):
            try:
                with affiliate_routing(code_filiale):
                    qs = (
                        Grand_Materiel.objects.using(filiale_db_name(code_filiale))
                        .select_related(
                            "code_sous_famille_materiel",
                            "code_type_marque",
                            "user_id",
                            "code_filiale_g",
                        )
                    )
                    qs = self.filter_queryset(qs)
                    paginator = self.paginator
                    page = paginator.paginate_queryset(qs, request, view=self)
                    if page is not None:
                        serializer = self.get_serializer(page, many=True)
                        return self.get_paginated_response(serializer.data)
                    serializer = self.get_serializer(qs, many=True)
                    return Response(serializer.data)
            except Exception:
                pass

        # Cross-filiale Journal Materiel: a user with administration.all_filiales
        # who did not target a specific filiale must see materiel from every
        # filiale database.
        if can_access_all_filiales(request.user) and not code_filiale:
            from django.conf import settings

            all_items = []
            for code in settings.FILIALE_DATABASES:
                with affiliate_routing(code):
                    qs = (
                        Grand_Materiel.objects.using(filiale_db_name(code))
                        .select_related(
                            "code_sous_famille_materiel",
                            "code_type_marque",
                            "user_id",
                            "code_filiale_g",
                        )
                    )
                    qs = self.filter_queryset(qs)
                    all_items.extend(list(qs))

            paginator = self.paginator
            page = paginator.paginate_queryset(all_items, request, view=self)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(all_items, many=True)
            return Response(serializer.data)

        return super().list(request, *args, **kwargs)

    serializer_class = GrandMaterielSerializer

    journal_module = JournalModules.MATERIEL

    journal_objet_type = "Grand_Materiel"

    journal_filiale_field = "code_filiale_g"

    permission_required = ("gestion.grand_materiel", "analyse.journal_materiel")

    search_fields = ["code_materiel", "designation", "num_serie", "immatriculation"]

    filter_backends = [GrandMaterielOrderingFilter, GrandMaterielFilter]

    ordering_fields = [
        "code_materiel",
        "designation",
        "num_serie",
        "immatriculation",
        "code_filiale_g",
        "code_sous_famille",
        "code_type_marque",
        "date_acquisition",
        "valeur_acquisition",
        "valeur_remplacement",
        "taux_amortissement",
        "puissance_materiel",
        "est_bloque",
        "libelle_famille",
        "libelle_categorie",
        "libelle_marque",
        "libelle_filiale",
        "libelle_sous_famille",
        "libelle_type_marque",
        "status",
    ]

    ordering = ["code_materiel"]

    def perform_create(self, serializer):

        with transaction.atomic():

            instance = serializer.save()

            extra = self.request.data

            code_site = extra.get("code_site")

            date_affectation = extra.get("date_affectation")

            date_debut_affectation = extra.get("date_debut_affectation")

            date_fin_affectation = extra.get("date_fin_affectation")

            prenable = extra.get("prenable")

            code_type_etat_materiel = extra.get("code_type_etat_materiel")

            date_situation = extra.get("date_situation")

            situation_est_bloque = extra.get("situation_est_bloque")

            type_situation_id = extra.get("type_situation_id")

            existing_count = Affectation_Materiel.objects.filter(
                code_materiel=instance
            ).count()

            code_affectation = f"{instance.code_materiel}.{(existing_count + 1):03d}"

            affectation = Affectation_Materiel.objects.create(
                code_affectation=code_affectation,
                code_materiel=instance,
                code_filiale_mere=instance.code_filiale_g,
                code_site_id=code_site if code_site else None,
                date_affectation=date_affectation or timezone.now(),
                date_debut_affectation=date_debut_affectation,
                date_fin_affectation=date_fin_affectation,
                prenable=bool(prenable),
                user_id=instance.user_id,
            )

            if type_situation_id:

                type_situation = Type_Situation.objects.get(id=type_situation_id)

            else:

                type_situation = Type_Situation.objects.get(
                    code_type_situation="CREATION"
                )

            type_etat = Type_Etat_Materiel.objects.get(
                code_type_etat_materiel=code_type_etat_materiel or "NEUF"
            )

            Situation_Materiel.objects.create(
                affectation_id=affectation,
                type_situation_id=type_situation,
                code_type_etat_materiel=type_etat,
                date_situation=date_situation or timezone.now(),
                est_bloque=bool(situation_est_bloque),
                user_id=instance.user_id,
            )

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
                description=f"CrÃÂ©ation de {self.journal_objet_type}",
            )


class MarqueMaterielViewSet(JournalisedModelViewSet):

    queryset = Marque_Materiel.objects.all()

    serializer_class = MarqueMaterielSerializer

    journal_module = JournalModules.MARQUE

    journal_objet_type = "Marque_Materiel"

    permission_required = "gestion.marques_materiel"

    search_fields = ["code_marque", "libelle_marque"]
    filter_backends = [MarqueMaterielFilter]

class TypeMarqueViewSet(JournalisedModelViewSet):

    queryset = Type_Marque.objects.all()

    serializer_class = TypeMarqueSerializer

    journal_module = JournalModules.TYPE_MARQUE

    journal_objet_type = "Type_Marque"

    permission_required = "gestion.types_marque"

    search_fields = ["code_type_marque", "libelle_type_marque"]
    search_fields = ["code_type_marque", "libelle_type_marque"]
    filter_backends = [TypeMarqueFilter]

class SousFamilleMaterielViewSet(JournalisedModelViewSet):

    queryset = Sous_Famille_Materiel.objects.all()

    serializer_class = SousFamilleMaterielSerializer

    journal_module = JournalModules.SOUS_FAMILLE

    journal_objet_type = "Sous_Famille_Materiel"

    permission_required = "gestion.sous_familles_materiel"
    search_fields = ["code_sous_famille", "libelle_sous_famille"]
    filter_backends = [SousFamilleMaterielFilter]
    search_fields = ["code_sous_famille", "libelle_sous_famille"]


class FamilleMaterielViewSet(JournalisedModelViewSet):

    queryset = Famille_Materiel.objects.all()

    serializer_class = FamilleMaterielSerializer

    journal_module = JournalModules.FAMILLE

    journal_objet_type = "Famille_Materiel"
    search_fields = ["code_famille", "libelle_famille"]
    filter_backends = [FamilleMaterielFilter]
    permission_required = "gestion.familles_materiel"

    search_fields = ["code_famille", "libelle_famille"]


class CategorieGMViewSet(JournalisedModelViewSet):

    queryset = Categorie_GM.objects.all()

    serializer_class = CategorieGMSerializer

    journal_module = JournalModules.CATEGORIE
    search_fields = ["code_categorie", "libelle_categorie"]
    filter_backends = [CategorieGMFilter]
    journal_objet_type = "Categorie_GM"

    permission_required = "gestion.categories_gm"

    search_fields = ["code_categorie", "libelle_categorie"]


class TypeAffectationViewSet(JournalisedModelViewSet):

    queryset = Type_Affectation.objects.all()

    serializer_class = TypeAffectationSerializer
    search_fields = ["code_type_affectation", "libelle_type_affectation"]
    filter_backends = [TypeAffectationFilter]
    journal_module = JournalModules.AFFECTATION

    journal_objet_type = "Type_Affectation"

    permission_required = "gestion.types_affectation"

    search_fields = ["code_type_affectation", "libelle_type_affectation"]


class TypeSituationViewSet(JournalisedModelViewSet):

    queryset = Type_Situation.objects.all()
    search_fields = ["code_type_situation", "libelle_type_situation"]
    filter_backends = [TypeSituationFilter]
    serializer_class = TypeSituationSerializer

    journal_module = JournalModules.SITUATION

    journal_objet_type = "Type_Situation"

    permission_required = "gestion.types_situation"

    search_fields = ["code_type_situation", "libelle_type_situation"]


class TypeEtatMaterielViewSet(JournalisedModelViewSet):
    search_fields = ["code_type_etat_materiel", "libelle_type_etat_materiel"]
    filter_backends = [TypeEtatMaterielFilter]
    queryset = Type_Etat_Materiel.objects.all()

    serializer_class = TypeEtatMaterielSerializer

    journal_module = JournalModules.TYPE_ETAT

    journal_objet_type = "Type_Etat_Materiel"

    permission_required = "gestion.types_etat_materiel"

    search_fields = ["code_type_etat_materiel", "libelle_type_etat_materiel"]


class SituationMaterielViewSet(JournalisedModelViewSet):

    def get_queryset(self):
        return Situation_Materiel.objects.all().select_related(
            "affectation_id",
            "affectation_id__code_materiel",
            "affectation_id__code_filiale_mere",
            "affectation_id__code_site",
            "type_situation_id",
            "type_situation_id__code_type_affectation",
            "code_type_etat_materiel",
            "user_id",
        )

    def list(self, request, *args, **kwargs):
        code_filiale = (
            request.query_params.get("filiale")
            or request.query_params.get("code_filiale")
        )
        if can_access_all_filiales(request.user) and not code_filiale:
            from django.conf import settings

            all_items = []
            for code in settings.FILIALE_DATABASES:
                with affiliate_routing(code):
                    qs = (
                        Situation_Materiel.objects.using(filiale_db_name(code))
                        .select_related(
                            "affectation_id",
                            "affectation_id__code_materiel",
                            "affectation_id__code_filiale_mere",
                            "affectation_id__code_site",
                            "type_situation_id",
                            "type_situation_id__code_type_affectation",
                            "code_type_etat_materiel",
                            "user_id",
                        )
                    )
                    qs = self.filter_queryset(qs)
                    all_items.extend(list(qs))

            paginator = self.paginator
            page = paginator.paginate_queryset(all_items, request, view=self)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(all_items, many=True)
            return Response(serializer.data)

        return super().list(request, *args, **kwargs)

    serializer_class = SituationMaterielSerializer

    journal_module = JournalModules.SITUATION

    journal_objet_type = "Situation_Materiel"

    permission_required = "gestion.situations"

    search_fields = ["id_situation", "affectation_id__code_materiel__code_materiel"]

    filter_backends = [OrderingFilter, SituationMaterielFilter]

    ordering_fields = [
        "date_situation",
        "id_situation",
        "est_bloque",
        "date_modification",
        "date_modification",
        "date_modification",
        "affectation_id__code_materiel__code_materiel",
        "affectation_id__code_filiale_mere__code_filiale",
        "affectation_id__code_site__code_site",
        "user_id__username",
        "type_situation_id__code_type_affectation",
        "type_situation_id__code_type_situation",
        "code_type_etat_materiel__code_type_etat_materiel",
    ]

    ordering = ["-date_situation"]




class EntrepriseViewSet(JournalisedModelViewSet):

    queryset = Entreprise.objects.all()

    serializer_class = EntrepriseSerializer

    journal_module = JournalModules.ADMINISTRATION

    journal_objet_type = "Entreprise"

    permission_required = "gestion.entreprises"


class FilialeViewSet(JournalisedModelViewSet):

    queryset = Filiale.objects.all()

    serializer_class = FilialeSerializer

    journal_module = JournalModules.ADMINISTRATION

    journal_objet_type = "Filiale"

    permission_required = "gestion.filiales"

    search_fields = ["code_filiale", "libelle_filiale"]
    filter_backends = [FilialeFilter]

    def get_queryset(self):
        qs = super().get_queryset()
        codes = get_allowed_filiale_codes(self.request.user)
        if codes:
            qs = qs.filter(code_filiale__in=codes)
        return qs


class AffectationMaterielViewSet(JournalisedModelViewSet):

    def get_queryset(self):
        return Affectation_Materiel.objects.all().select_related(
            "code_materiel",
            "code_filiale_mere",
            "code_site",
            "user_id",
        )

    def list(self, request, *args, **kwargs):
        code_filiale = (
            request.query_params.get("filiale")
            or request.query_params.get("code_filiale")
        )
        if can_access_all_filiales(request.user) and not code_filiale:
            from django.conf import settings

            all_items = []
            for code in settings.FILIALE_DATABASES:
                with affiliate_routing(code):
                    qs = (
                        Affectation_Materiel.objects.using(filiale_db_name(code))
                        .select_related(
                            "code_materiel",
                            "code_filiale_mere",
                            "code_site",
                            "user_id",
                        )
                    )
                    qs = self.filter_queryset(qs)
                    all_items.extend(list(qs))

            paginator = self.paginator
            page = paginator.paginate_queryset(all_items, request, view=self)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(all_items, many=True)
            return Response(serializer.data)

        return super().list(request, *args, **kwargs)

    serializer_class = AffectationMaterielSerializer

    journal_module = JournalModules.AFFECTATION

    journal_objet_type = "Affectation_Materiel"

    journal_filiale_field = "code_filiale_mere"

    journal_site_field = "code_site"

    permission_required = "gestion.affectations"

    search_fields = [
        "code_affectation",
        "code_materiel__code_materiel",
        "code_site__code_site",
    ]

    filter_backends = [OrderingFilter, AffectationMaterielFilter]

    ordering_fields = [
        "code_affectation",
        "date_affectation",
        "est_bloque",
        "nbr_jours_affectation",
        "code_materiel__code_materiel",
        "code_filiale_mere__code_filiale",
        "code_site__code_site",
    ]

    ordering = ["-date_affectation"]


class PointageViewSet(JournalisedModelViewSet):

    def get_queryset(self):
        return Pointage.objects.all().select_related(
            "affectation_id",
            "affectation_id__code_materiel",
            "affectation_id__code_site",
            "affectation_id__code_filiale_mere",
            "user_id",
        )

    def list(self, request, *args, **kwargs):
        code_filiale = (
            request.query_params.get("filiale")
            or request.query_params.get("code_filiale")
        )
        if can_access_all_filiales(request.user) and not code_filiale:
            from django.conf import settings

            all_items = []
            for code in settings.FILIALE_DATABASES:
                with affiliate_routing(code):
                    qs = (
                        Pointage.objects.using(filiale_db_name(code))
                        .select_related(
                            "affectation_id",
                            "affectation_id__code_materiel",
                            "affectation_id__code_site",
                            "affectation_id__code_filiale_mere",
                            "user_id",
                        )
                    )
                    qs = self.filter_queryset(qs)
                    all_items.extend(list(qs))

            paginator = self.paginator
            page = paginator.paginate_queryset(all_items, request, view=self)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(all_items, many=True)
            return Response(serializer.data)

        return super().list(request, *args, **kwargs)

    serializer_class = PointageSerializer

    journal_module = JournalModules.POINTAGE

    journal_objet_type = "Pointage"

    permission_required = "gestion.pointages"

    search_fields = ["affectation_id__code_affectation", "mmaa"]

    filter_backends = [PointageOrderingFilter, PointageFilter]

    ordering_fields = [
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
        "created_at",
        "updated_at",
        "user",
        "code_affectation",
        "code_materiel",
        "code_site",
        "code_filiale",
        "user_id__username",
        "affectation_id__code_affectation",
        "affectation_id__code_materiel__code_materiel",
        "affectation_id__code_filiale_mere__code_filiale",
        "affectation_id__code_site__code_site",
        "montant_service",
        "montant_chomage",
        "montant_panne",
        "date_modification",
        "est_bloque",
        "created_at",
        "updated_at",
        "user",
        "code_affectation",
        "code_materiel",
        "code_site",
        "code_filiale",
        "user_id__username",
        "affectation_id__code_affectation",
        "affectation_id__code_materiel__code_materiel",
        "affectation_id__code_filiale_mere__code_filiale",
        "affectation_id__code_site__code_site",
    ]

    ordering = ["-mmaa", "-date_modification"]


class RegularisationGMViewSet(JournalisedModelViewSet):

    def get_queryset(self):
        return Regularisation_GM.objects.all().select_related("code_site", "user_id")

    def list(self, request, *args, **kwargs):
        code_filiale = (
            request.query_params.get("filiale")
            or request.query_params.get("code_filiale")
        )
        if can_access_all_filiales(request.user) and not code_filiale:
            from django.conf import settings

            all_items = []
            for code in settings.FILIALE_DATABASES:
                with affiliate_routing(code):
                    qs = (
                        Regularisation_GM.objects.using(filiale_db_name(code))
                        .select_related("code_site", "user_id")
                    )
                    qs = self.filter_queryset(qs)
                    all_items.extend(list(qs))

            paginator = self.paginator
            page = paginator.paginate_queryset(all_items, request, view=self)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(all_items, many=True)
            return Response(serializer.data)

        return super().list(request, *args, **kwargs)

    serializer_class = RegularisationGMSerializer

    journal_module = JournalModules.REGULARISATION

    journal_objet_type = "Regularisation_GM"

    journal_site_field = "code_site"

    permission_required = "gestion.regularisations_gm"

    search_fields = ["code_regularisation"]
    filter_backends = [RegularisationGMFilter]

    search_fields = ["code_site__code_site", "mmaa"]


class RegularisationMoisGM2ViewSet(JournalisedModelViewSet):

    def get_queryset(self):
        return Regularisation_Mois_GM2.objects.all()

    serializer_class = RegularisationMoisGM2Serializer

    journal_module = JournalModules.REGULARISATION
    search_fields = ["code_regularisation"]
    filter_backends = [RegularisationMoisGM2Filter]
    journal_objet_type = "Regularisation_Mois_GM2"

    permission_required = "gestion.regularisations_mois"

    search_fields = ["code_regularisation"]



class DivisionViewSet(JournalisedModelViewSet):

    queryset = Division.objects.all()

    serializer_class = DivisionSerializer

    journal_module = JournalModules.ADMINISTRATION

    journal_objet_type = "Division"

    permission_required = "gestion.divisions"

    search_fields = ["code_division", "libelle_division"]
    filter_backends = [DivisionFilter]


class FamilleStructuresViewSet(JournalisedModelViewSet):

    queryset = Famille_Structures.objects.all()

    serializer_class = FamilleStructuresSerializer

    journal_module = JournalModules.ADMINISTRATION

    journal_objet_type = "Famille_Structures"

    permission_required = "gestion.familles_structures"

    search_fields = ["code_famille_structure", "libelle_famille_structure"]
    filter_backends = [FamilleStructuresFilter]


class SiteViewSet(JournalisedModelViewSet):

    queryset = Site.objects.all()

    serializer_class = SiteSerializer
    search_fields = ["code_site", "libelle_site", "code_region"]
    filter_backends = [SiteFilter]
    journal_module = JournalModules.SITE

    journal_objet_type = "Site"

    journal_filiale_field = "code_filiale"

    permission_required = "gestion.sites"

    search_fields = ["code_site", "libelle_site", "code_region"]


def pointage_upload_view(request):

    # this used to import csv pointage data from db (features bulk import to make it faster)

    if request.method == "POST":

        file_obj = request.FILES["file"]

        service = PointageImportService(file_obj)

        service.import_data()

        return JsonResponse(
            {"success": True, "message": "Import completed successfully"}
        )

    return render(request, "pointage_upload.html")


def situation_upload_view(request):

    if request.method == "POST":

        file_obj = request.FILES["file"]

        service = SituationImportService(file_obj)

        service.import_data()

        return JsonResponse(
            {"success": True, "message": "Import completed successfully"}
        )

    return render(request, "situation_upload.html")


class TP_AQ_API_View(PagePermissionRequiredMixin, APIView):

    permission_required = "analyse.quantitative"

    def get(self, request):

        code_filiale = request.query_params.get("code_filiale")

        date_debut = request.query_params.get("date_debut")

        date_fin = request.query_params.get("date_fin")

        include_pending = (
            request.query_params.get("include_pending", "false").lower() == "true"
        ) and can_include_pending_data(request.user)

        # Validate that the requested filiale is within the user's scope.
        if code_filiale and not can_access_filiale(request.user, code_filiale):
            return Response(
                {"detail": "Accès refusé à cette filiale."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if code_filiale:

            using = filiale_db_name(code_filiale)

            data = AnalyseQuantitative.get_situations(
                code_filiale=code_filiale,
                date_debut=date_debut,
                date_fin=date_fin,
                include_pending=include_pending,
                using=using,
            )

        elif can_access_all_filiales(request.user):

            # Cross-filiale user with no filiale filter: query every filiale DB and merge.

            from django.conf import settings

            all_rows = []

            for code in settings.FILIALE_DATABASES:

                using = filiale_db_name(code)

                rows = AnalyseQuantitative.get_situations(
                    code_filiale=None,
                    date_debut=date_debut,
                    date_fin=date_fin,
                    include_pending=include_pending,
                    using=using,
                )

                all_rows.extend(rows)

            data = all_rows

        else:

            # Filiale user: let the router resolve the DB from thread-local.

            data = AnalyseQuantitative.get_situations(
                code_filiale=code_filiale,
                date_debut=date_debut,
                date_fin=date_fin,
                include_pending=False,
                using=None,
            )

        return Response(data)


class TP_AQ_resume_API_View(PagePermissionRequiredMixin, APIView):

    permission_required = "analyse.quantitative"

    def get(self, request):

        code_filiale = request.query_params.get("code_filiale")

        date_debut = request.query_params.get("date_debut")

        date_fin = request.query_params.get("date_fin")

        include_pending = request.query_params.get(
            "include_pending", "false"
        ).lower() == "true" and can_include_pending_data(request.user)

        if code_filiale and not can_access_filiale(request.user, code_filiale):
            return Response(
                {"detail": "Accès refusé à cette filiale."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if code_filiale:

            using = filiale_db_name(code_filiale)

            data = AnalyseQuantitativeResume.get_situations_resume(
                code_filiale=code_filiale,
                date_debut=date_debut,
                date_fin=date_fin,
                include_pending=include_pending,
                using=using,
            )

        elif can_access_all_filiales(request.user):

            from django.conf import settings

            total = 0

            age_total = 0

            devider = 0

            exp_service = 0

            exp_chomage = 0

            exp_panne = 0

            imm_chomage = 0

            imm_reparation = 0

            imm_autre = 0

            rep_ALREM = 0

            rep_autre = 0

            for code in settings.FILIALE_DATABASES:

                using = filiale_db_name(code)

                row = AnalyseQuantitativeResume.get_situations_resume(
                    code_filiale=None,
                    date_debut=date_debut,
                    date_fin=date_fin,
                    include_pending=include_pending,
                    using=using,
                )

                total += row["nombre_totale"]

                age_total += row["age_moyen"]  # placeholder, recompute below

                exp_service += row["exploitation"]["en_service"]

                exp_chomage += row["exploitation"]["en_chomage"]

                exp_panne += row["exploitation"]["en_panne"]

                imm_chomage += row["immobilises"]["en_chomage"]

                imm_reparation += row["immobilises"]["en_reparation"]

                imm_autre += row["immobilises"]["autre"]

                rep_ALREM += row["reparation_externe"]["ALREM"]

                rep_autre += row["reparation_externe"]["autre"]

            data = {

                "nombre_totale": total,

                "age_moyen": int(age_total / len(settings.FILIALE_DATABASES)) if settings.FILIALE_DATABASES else 0,

                "exploitation": {

                    "en_service": exp_service,

                    "en_chomage": exp_chomage,

                    "en_panne": exp_panne,

                },

                "immobilises": {

                    "en_chomage": imm_chomage,

                    "en_reparation": imm_reparation,

                    "autre": imm_autre,

                },

                "reparation_externe": {

                    "ALREM": rep_ALREM,

                    "autre": rep_autre,

                },

            }

        else:

            data = AnalyseQuantitativeResume.get_situations_resume(
                code_filiale=code_filiale,

                date_debut=date_debut,

                date_fin=date_fin,

                include_pending=False,

                using=None,

            )

        return Response(data)


class TP_AE_API_View(PagePermissionRequiredMixin, APIView):

    permission_required = "analyse.exploitation"

    def get(self, request):

        code_filiale = request.query_params.get("code_filiale")

        date_debut = request.query_params.get("date_debut")

        date_fin = request.query_params.get("date_fin")

        include_pending = request.query_params.get(
            "include_pending", "false"
        ).lower() == "true" and can_include_pending_data(request.user)

        if code_filiale and not can_access_filiale(request.user, code_filiale):
            return Response(
                {"detail": "Accès refusé à cette filiale."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if code_filiale:

            using = filiale_db_name(code_filiale)

            data = AnalyseExploitation.get_pointages(
                code_filiale=code_filiale,
                date_debut=date_debut,
                date_fin=date_fin,
                include_pending=include_pending,
                using=using,
            )

        elif can_access_all_filiales(request.user):

            from django.conf import settings

            all_rows = []

            for code in settings.FILIALE_DATABASES:

                using = filiale_db_name(code)

                rows = AnalyseExploitation.get_pointages(
                    code_filiale=None,

                    date_debut=date_debut,

                    date_fin=date_fin,

                    include_pending=include_pending,

                    using=using,

                )

                all_rows.extend(rows)

            all_rows.sort(key=lambda row: (row["code_sous_famille"] or ""))

            data = all_rows

        else:

            data = AnalyseExploitation.get_pointages(
                code_filiale=code_filiale,

                date_debut=date_debut,

                date_fin=date_fin,

                include_pending=False,

                using=None,

            )

        return Response(data)


class TP_AE_resume_API_View(PagePermissionRequiredMixin, APIView):

    permission_required = "analyse.exploitation"

    def get(self, request):

        code_filiale = request.query_params.get("code_filiale")

        date_debut = request.query_params.get("date_debut")

        date_fin = request.query_params.get("date_fin")

        include_pending = request.query_params.get(
            "include_pending", "false"
        ).lower() == "true" and can_include_pending_data(request.user)

        if code_filiale and not can_access_filiale(request.user, code_filiale):
            return Response(
                {"detail": "Accès refusé à cette filiale."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if code_filiale:

            using = filiale_db_name(code_filiale)

            data = AnalyseExploitationResume.get_pointages_resume(
                code_filiale=code_filiale,
                date_debut=date_debut,
                date_fin=date_fin,
                include_pending=include_pending,
                using=using,
            )

        elif can_access_all_filiales(request.user):

            from django.conf import settings

            nombre_existant = 0

            nombre_pointage = 0

            nombre_materiels_pointes = 0

            heures_service = 0

            heures_chomage = 0

            heures_panne = 0

            montant_service = 0

            montant_chomage = 0

            montant_panne = 0

            total_potentiel = 0

            total_potentiel_enregistre = 0

            total_potentiel_calcule = 0

            total_taux = 0

            for code in settings.FILIALE_DATABASES:

                using = filiale_db_name(code)

                row = AnalyseExploitationResume.get_pointages_resume(
                    code_filiale=None,

                    date_debut=date_debut,

                    date_fin=date_fin,

                    include_pending=include_pending,

                    using=using,

                )

                nombre_existant += row["nombre_existant"]

                nombre_pointage += row["nombre_pointage"]

                nombre_materiels_pointes += row["nombre_materiels_pointes"]

                heures_service += row["heures_service"]

                heures_chomage += row["heures_chomage"]

                heures_panne += row["heures_panne"]

                montant_service += row["montant_service"]

                montant_chomage += row["montant_chomage"]

                montant_panne += row["montant_panne"]

                total_potentiel += row["total_potentiel"]

                total_potentiel_enregistre += row["total_potentiel_enregistre"]

                total_potentiel_calcule += row["total_potentiel_calcule"]

                total_taux += row["taux_location_moyen"] * row["nombre_pointage"]

            total_heures = heures_service + heures_chomage + heures_panne

            total_montants = montant_service + montant_chomage + montant_panne

            data = {

                "nombre_existant": nombre_existant,

                "nombre_pointage": nombre_pointage,

                "nombre_materiels_pointes": nombre_materiels_pointes,

                "heures_service": heures_service,

                "heures_chomage": heures_chomage,

                "heures_panne": heures_panne,

                "montant_service": montant_service,

                "montant_chomage": montant_chomage,

                "montant_panne": montant_panne,

                "potentiel_moyen": (

                    total_potentiel / nombre_pointage if nombre_pointage else 0

                ),

                "total_potentiel": total_potentiel,

                "total_potentiel_enregistre": total_potentiel_enregistre,

                "total_potentiel_calcule": total_potentiel_calcule,

                "taux_location_moyen": (

                    total_taux / nombre_pointage if nombre_pointage else 0

                ),

                "pct_heures_service": (

                    heures_service * 100 / total_heures if total_heures else 0

                ),

                "pct_heures_chomage": (

                    heures_chomage * 100 / total_heures if total_heures else 0

                ),

                "pct_heures_panne": (

                    heures_panne * 100 / total_heures if total_heures else 0

                ),

                "pct_montant_service": (

                    montant_service * 100 / total_montants if total_montants else 0

                ),

                "pct_montant_chomage": (

                    montant_chomage * 100 / total_montants if total_montants else 0

                ),

                "pct_montant_panne": (

                    montant_panne * 100 / total_montants if total_montants else 0

                ),

            }

        else:

            data = AnalyseExploitationResume.get_pointages_resume(
                code_filiale=code_filiale,

                date_debut=date_debut,

                date_fin=date_fin,

                include_pending=False,

                using=None,

            )

        return Response(data)


class DashboardMaterialDetailsAPIView(PagePermissionRequiredMixin, APIView):
    """



    GET /api/dashboard/material-details/



    Query params:



      code_filiale (optional)



      date_debut (optional, YYYY-MM-DD): start of period



      date_fin (optional, YYYY-MM-DD): end of period



      code_famille (optional)



      search (optional)



      page (optional, default 1)



      page_size (optional, default 50)



    """

    permission_required = "analyse.dashboard"

    def get(self, request):

        code_filiale = request.query_params.get("code_filiale")

        date_debut = request.query_params.get("date_debut")

        date_fin = request.query_params.get("date_fin")

        code_famille = request.query_params.get("code_famille")

        search = request.query_params.get("search")

        page = int(request.query_params.get("page", 1))

        page_size = int(request.query_params.get("page_size", 50))

        from django.conf import settings
        from django.db import models as _m

        def _build_qs(using=None):
            base = Grand_Materiel.objects
            if using is not None:
                base = base.using(using)
            q = base.filter(est_bloque=False).select_related(
                "code_sous_famille_materiel",
                "code_sous_famille_materiel__code_famille_materiel",
                "code_type_marque",
                "code_filiale_g",
            )
            if code_filiale:
                q = q.filter(code_filiale_g=code_filiale)
            if code_famille:
                q = q.filter(
                    code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
                )
            if search:
                q = q.filter(
                    Q(code_materiel__icontains=search)
                    | Q(designation__icontains=search)
                    | Q(code_type_marque__code_type_marque__icontains=search)
                )
            return q

        from api.permissions import can_access_all_filiales
        if can_access_all_filiales(request.user) and not code_filiale:
            all_items = []
            for code in settings.FILIALE_DATABASES:
                using = f"filiale_{code}"
                qs_db = _build_qs(using=using)
                all_items.extend(list(qs_db))
            total = len(all_items)
            start = (page - 1) * page_size
            end = start + page_size
            items = all_items[start:end]
        else:
            qs = _build_qs()
            total = qs.count()
            start = (page - 1) * page_size
            end = start + page_size
            items = qs[start:end]

        result = []

        for gm in items:

            sous_famille = gm.code_sous_famille_materiel

            famille = sous_famille.code_famille_materiel if sous_famille else None

            result.append(
                {
                    "code_materiel": gm.code_materiel,
                    "designation": gm.designation,
                    "code_sous_famille": (
                        sous_famille.code_sous_famille if sous_famille else ""
                    ),
                    "libelle_sous_famille": (
                        sous_famille.libelle_sous_famille if sous_famille else ""
                    ),
                    "code_famille": famille.code_famille if famille else "",
                    "libelle_famille": famille.libelle_famille if famille else "",
                    "code_type_marque": (
                        gm.code_type_marque.code_type_marque
                        if gm.code_type_marque
                        else ""
                    ),
                    "libelle_type_marque": (
                        gm.code_type_marque.libelle_type_marque
                        if gm.code_type_marque
                        else ""
                    ),
                    "code_filiale": (
                        gm.code_filiale_g.code_filiale if gm.code_filiale_g else ""
                    ),
                    "libelle_filiale": (
                        gm.code_filiale_g.libelle_filiale if gm.code_filiale_g else ""
                    ),
                    "est_bloque": gm.est_bloque,
                }
            )

        return Response(
            {
                "items": result,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )


class ValidatePointageView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.pointage"

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
                    "message": "Aucun fichier reÃÂ§u.",
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

        if filiale and not can_access_filiale(request.user, filiale):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

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


class ImportPointageView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.pointage"

    parser_classes = [JSONParser]

    def post(self, request):

        import logging
        logger = logging.getLogger(__name__)

        try:
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

            # The import writes into the affiliate recorded at validation

            # time: the user must be allowed to write into it.

            _validation_payload = ValidationCache.get(validation_id)

            _import_filiale = (_validation_payload or {}).get("filiale")

            if _import_filiale and not can_access_filiale(

                request.user, _import_filiale

            ):

                return Response(
                    {
                        "success": False,
                        "message": "Accès refusé à cette filiale.",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # -----------------------------------------------------

            # 2. Import already validated rows

            # -----------------------------------------------------

            try:

                importer = PointageCsvImporter(
                    validation_id=validation_id,
                    user=request.user,
                )

                result = importer.import_data()

                logger.info(f"ImportPointageView result: {result}")

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

            except Exception as exc:
                logger.error(f"ImportPointageView import_data failed: {exc}", exc_info=True)
                return Response(
                    {
                        "success": False,
                        "message": "Une erreur inattendue est survenue pendant l'import.",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # -----------------------------------------------------

            # Notify admins about pending imports

            # -----------------------------------------------------

            try:

                notify_pending_import(
                    request=request,
                    result=result,
                    module_name="Pointage",
                )

            except Exception as e:

                logger.error(f"notify_pending_import failed: {e}", exc_info=True)

            # Build response data - ensure no model instances
            response_data = {
                "success": result.get("success", True),
                "imported_rows": result.get("imported_rows", 0),
                "filiale": result.get("filiale"),
                "filename": result.get("filename"),
                "validation_summary": result.get("validation_summary"),
                "import_batch_id": result.get("import_batch_id"),
                "message": "Import terminé avec succès.",
            }

            return Response(
                response_data,
                status=status.HTTP_201_CREATED,
            )

        except Exception as exc:
            logger.error(f"ImportPointageView post failed: {exc}", exc_info=True)
            return Response(
                {
                    "success": False,
                    "message": "Une erreur inattendue est survenue.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ValidateGrandMaterielView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.grand_materiel"

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
                    "message": "Aucun fichier reÃÂ§u.",
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

        if filiale and not can_access_filiale(request.user, filiale):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
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


class ImportGrandMaterielView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.grand_materiel"

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

        # The import writes into the affiliate recorded at validation

        # time: the user must be allowed to write into it.

        _validation_payload = ValidationCache.get(validation_id)

        _import_filiale = (_validation_payload or {}).get("filiale")

        if _import_filiale and not can_access_filiale(

            request.user, _import_filiale

        ):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # -----------------------------------------------------

        # 2. Import validated rows

        # -----------------------------------------------------

        try:

            importer = GMCsvImporter(
                validation_id=validation_id,
                user=request.user,
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

        except Exception as exc:

            views_logger.error(
                f"{self.__class__.__name__} import failed: {exc}",
                exc_info=True,
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue " "pendant l'import."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -----------------------------------------------------

        # 3. Successful import

        # -----------------------------------------------------

        # -----------------------------------------------------

        # Notify admins about pending imports

        # -----------------------------------------------------

        try:

            notify_pending_import(
                request=request,
                result=result,
                module_name="Grand Matériel",
            )

        except Exception as e:

            import logging

            logger = logging.getLogger(__name__)

            logger.error(f"notify_pending_import failed: {e}", exc_info=True)

        return Response(
            {
                **result,
                "message": "Import Terminé avec Succès.",
            },
            status=status.HTTP_201_CREATED,
        )


class ValidateMarqueView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.marque"

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
                    "message": "Aucun fichier reÃÂ§u.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------

        # 2. Selected filiale

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

        if filiale and not can_access_filiale(request.user, filiale):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
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

        # 3. Validate CSV

        # -----------------------------------------------------

        try:

            validator = MarqueCsvValidator(
                uploaded_file=file,
                schema=MARQUE_MATERIEL_SCHEMA,
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

        # 4. Build response

        # -----------------------------------------------------

        response_data = report.to_dict()

        # -----------------------------------------------------

        # 5. Cache successful validation

        # -----------------------------------------------------

        if report.success:

            validation_id = ValidationCache.save(
                report=report,
                filiale=filiale,
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


class ImportMarqueView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.marque"

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

        # The import writes into the affiliate recorded at validation

        # time: the user must be allowed to write into it.

        _validation_payload = ValidationCache.get(validation_id)

        _import_filiale = (_validation_payload or {}).get("filiale")

        if _import_filiale and not can_access_filiale(

            request.user, _import_filiale

        ):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
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

        except Exception as exc:

            views_logger.error(
                f"{self.__class__.__name__} import failed: {exc}",
                exc_info=True,
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue " "pendant l'import."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -----------------------------------------------------

        # 3. Successful import

        # -----------------------------------------------------

        # -----------------------------------------------------

        # Notify admins about pending imports

        # -----------------------------------------------------

        try:

            notify_pending_import(
                request=request,
                result=result,
                module_name="Marque",
            )

        except Exception as e:

            import logging

            logger = logging.getLogger(__name__)

            logger.error(f"notify_pending_import failed: {e}", exc_info=True)

        return Response(
            {
                **result,
                "message": "Import Terminé avec Succès.",
            },
            status=status.HTTP_201_CREATED,
        )


class ValidateTypeMarqueView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.type_marque"

    parser_classes = [MultiPartParser]

    def post(self, request):

        pass

        # -----------------------------------------------------

        # 1. Uploaded file

        # -----------------------------------------------------

        file = request.FILES.get("file")

        if file is None:

            return Response(
                {
                    "success": False,
                    "message": "Aucun fichier reÃÂ§u.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------

        # 2. Selected filiale

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

        if filiale and not can_access_filiale(request.user, filiale):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
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

        # 3. Validate CSV

        # -----------------------------------------------------

        try:

            validator = TypeMarqueCsvValidator(
                uploaded_file=file,
                schema=TYPE_MARQUE_SCHEMA,
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

        # 4. Build response

        # -----------------------------------------------------

        response_data = report.to_dict()

        # -----------------------------------------------------

        # 5. Cache successful validation

        # -----------------------------------------------------

        if report.success:

            validation_id = ValidationCache.save(
                report=report,
                filiale=filiale,
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


class ImportTypeMarqueView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.type_marque"

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

        # The import writes into the affiliate recorded at validation

        # time: the user must be allowed to write into it.

        _validation_payload = ValidationCache.get(validation_id)

        _import_filiale = (_validation_payload or {}).get("filiale")

        if _import_filiale and not can_access_filiale(

            request.user, _import_filiale

        ):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # -----------------------------------------------------

        # 2. Import validated rows

        # -----------------------------------------------------

        try:

            importer = TypeMarqueCsvImporter(
                validation_id=validation_id,
                user=request.user,
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

        except Exception as exc:

            views_logger.error(
                f"{self.__class__.__name__} import failed: {exc}",
                exc_info=True,
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue " "pendant l'import."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -----------------------------------------------------

        # 3. Successful import

        # -----------------------------------------------------

        # -----------------------------------------------------

        # Notify admins about pending imports

        # -----------------------------------------------------

        try:

            notify_pending_import(
                request=request,
                result=result,
                module_name="Type Marque",
            )

        except Exception as e:

            import logging

            logger = logging.getLogger(__name__)

            logger.error(f"notify_pending_import failed: {e}", exc_info=True)

        return Response(
            {
                **result,
                "message": "Import Terminé avec Succès.",
            },
            status=status.HTTP_201_CREATED,
        )


class ValidateSousFamilleView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.sous_famille"

    parser_classes = [MultiPartParser]

    def post(self, request):

        pass

        # -----------------------------------------------------

        # 1. Uploaded file

        # -----------------------------------------------------

        file = request.FILES.get("file")

        if file is None:

            return Response(
                {
                    "success": False,
                    "message": "Aucun fichier reÃÂ§u.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------

        # 2. Selected filiale

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

        if filiale and not can_access_filiale(request.user, filiale):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
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

        # 3. Validate CSV

        # -----------------------------------------------------

        try:

            validator = SousFamilleCsvValidator(
                uploaded_file=file,
                schema=SOUS_FAMILLE_SCHEMA,
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

        # 4. Build response

        # -----------------------------------------------------

        response_data = report.to_dict()

        # -----------------------------------------------------

        # 5. Cache successful validation

        # -----------------------------------------------------

        if report.success:

            validation_id = ValidationCache.save(
                report=report,
                filiale=filiale,
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


class ImportSousFamilleView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.sous_famille"

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

        # The import writes into the affiliate recorded at validation

        # time: the user must be allowed to write into it.

        _validation_payload = ValidationCache.get(validation_id)

        _import_filiale = (_validation_payload or {}).get("filiale")

        if _import_filiale and not can_access_filiale(

            request.user, _import_filiale

        ):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # -----------------------------------------------------

# 2. Import validated rows

        # -----------------------------------------------------

        try:

            importer = SousFamilleCsvImporter(
                validation_id=validation_id,
                user=request.user,
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

        except Exception as exc:

            views_logger.error(
                f"{self.__class__.__name__} import failed: {exc}",
                exc_info=True,
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue " "pendant l'import."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -----------------------------------------------------

        # 3. Successful import

        # -----------------------------------------------------

        # -----------------------------------------------------

        # Notify admins about pending imports

        # -----------------------------------------------------

        try:

            notify_pending_import(
                request=request,
                result=result,
                module_name="Sous Famille",
            )

        except Exception as e:

            import logging

            logger = logging.getLogger(__name__)

            logger.error(f"notify_pending_import failed: {e}", exc_info=True)

        return Response(
            {
                **result,
                "message": "Import Terminé avec Succès.",
            },
            status=status.HTTP_201_CREATED,
        )


class ValidateFamilleView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.famille"

    parser_classes = [MultiPartParser]

    def post(self, request):

        file = request.FILES.get("file")

        if file is None:

            return Response(
                {
                    "success": False,
                    "message": "Aucun fichier reÃÂ§u.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------

        # 2. Selected filiale

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

        if filiale and not can_access_filiale(request.user, filiale):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

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

            validator = FamilleCsvValidator(
                uploaded_file=file,
                schema=FAMILLE_SCHEMA,
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


class ImportFamilleView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.famille"

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

        # The import writes into the affiliate recorded at validation

        # time: the user must be allowed to write into it.

        _validation_payload = ValidationCache.get(validation_id)

        _import_filiale = (_validation_payload or {}).get("filiale")

        if _import_filiale and not can_access_filiale(

            request.user, _import_filiale

        ):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:

            importer = FamilleCsvImporter(
                validation_id=validation_id,
                user=request.user,
            )

            result = importer.import_data()

            try:

                log_csv_import(
                    request,
                    result,
                    JournalModules.FAMILLE,
                )

            except Exception:

                pass

        except FamilleValidationExpiredError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_410_GONE,
            )

        except FamilleImportError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except Exception as exc:

            views_logger.error(
                f"{self.__class__.__name__} import failed: {exc}",
                exc_info=True,
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue " "pendant l'import."
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


class ValidateCategorieGMView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.categorie_gm"

    parser_classes = [MultiPartParser]

    def post(self, request):

        file = request.FILES.get("file")

        if file is None:

            return Response(
                {
                    "success": False,
                    "message": "Aucun fichier reÃÂ§u.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------

        # 2. Selected filiale

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

        if filiale and not can_access_filiale(request.user, filiale):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

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

            validator = CategorieGMCsvValidator(
                uploaded_file=file,
                schema=CATEGORIE_GM_SCHEMA,
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


class ImportCategorieGMView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.categorie_gm"

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

        # The import writes into the affiliate recorded at validation

        # time: the user must be allowed to write into it.

        _validation_payload = ValidationCache.get(validation_id)

        _import_filiale = (_validation_payload or {}).get("filiale")

        if _import_filiale and not can_access_filiale(

            request.user, _import_filiale

        ):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:

            importer = CategorieGMCsvImporter(
                validation_id=validation_id,
                user=request.user,
            )

            result = importer.import_data()

            try:

                log_csv_import(
                    request,
                    result,
                    JournalModules.CATEGORIE,
                )

            except Exception:

                pass

        except CategorieGMValidationExpiredError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_410_GONE,
            )

        except CategorieGMImportError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except Exception as exc:

            views_logger.error(
                f"{self.__class__.__name__} import failed: {exc}",
                exc_info=True,
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue " "pendant l'import."
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


class ValidateSituationAffectationView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.situation_affectation"

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
                    "message": "Aucun fichier reÃÂ§u.",
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

        if filiale and not can_access_filiale(request.user, filiale):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
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


class ImportSituationAffectationView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.situation_affectation"

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

        # The import writes into the affiliate recorded at validation

        # time: the user must be allowed to write into it.

        _validation_payload = ValidationCache.get(validation_id)

        _import_filiale = (_validation_payload or {}).get("filiale")

        if _import_filiale and not can_access_filiale(

            request.user, _import_filiale

        ):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # -----------------------------------------------------

        # 3. Import validated rows

        # -----------------------------------------------------

        try:

            importer = SituationAffectationCsvImporter(
                validation_id=validation_id,
                user=request.user,
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

        except Exception as exc:

            views_logger.error(
                f"{self.__class__.__name__} import failed: {exc}",
                exc_info=True,
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue " "pendant l'import."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -----------------------------------------------------

        # Notify admins about pending imports

        # -----------------------------------------------------

        try:

            notify_pending_import(
                request=request,
                result=result,
                module_name="Situation Affectation",
            )

        except Exception as e:

            import logging

            logger = logging.getLogger(__name__)

            logger.error(f"notify_pending_import failed: {e}", exc_info=True)

        # -----------------------------------------------------

        # 3. Successful import

        # -----------------------------------------------------

        # -----------------------------------------------------

        # Notify admins about pending imports

        # -----------------------------------------------------

        try:

            notify_pending_import(
                request=request,
                result=result,
                module_name="Situation Affectation",
            )

        except Exception as e:

            import logging

            logger = logging.getLogger(__name__)

            logger.error(f"notify_pending_import failed: {e}", exc_info=True)

        return Response(
            {
                **result,
                "message": "Import terminé avec succès.",
            },
            status=status.HTTP_201_CREATED,
        )


class ValidateRegularisationGMView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.regularisation"

    parser_classes = [MultiPartParser]

    def post(self, request):

        file = request.FILES.get("file")

        if file is None:

            return Response(
                {
                    "success": False,
                    "message": "Aucun fichier reÃÂ§u.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------

        # 2. Selected filiale

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

        if filiale and not can_access_filiale(request.user, filiale):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
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


class ImportRegularisationGMView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.regularisation"

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

        # The import writes into the affiliate recorded at validation

        # time: the user must be allowed to write into it.

        _validation_payload = ValidationCache.get(validation_id)

        _import_filiale = (_validation_payload or {}).get("filiale")

        if _import_filiale and not can_access_filiale(

            request.user, _import_filiale

        ):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:

            importer = RegularisationGMCsvImporter(
                validation_id=validation_id,
                user=request.user,
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

        except Exception as exc:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"ImportRegularisationGMView import_data failed: {exc}", exc_info=True)
            return Response(
                {
                    "success": False,
                    "message": "Une erreur inattendue est survenue pendant l'import.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -----------------------------------------------------
        # Notify admins about pending imports
        # -----------------------------------------------------

        try:
            notify_pending_import(
                request=request,
                result=result,
                module_name="Régularisation GM",
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"notify_pending_import failed: {e}", exc_info=True)

        # Build response data - ensure no model instances
        response_data = {
            "success": result.get("success", True),
            "imported_rows": result.get("imported_rows", 0),
            "filiale": result.get("filiale"),
            "filename": result.get("filename"),
            "validation_summary": result.get("validation_summary"),
            "import_batch_id": result.get("import_batch_id"),
            "message": "Import Terminé avec Succès.",
        }

        return Response(
            response_data,
            status=status.HTTP_201_CREATED,
        )


class ValidateSiteView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.site"

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
                    "message": "Aucun fichier reÃÂ§u.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------

        # 2. Selected filiale

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

        if filiale and not can_access_filiale(request.user, filiale):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
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

        # 3. Validate CSV

        # -----------------------------------------------------

        try:

            validator = SiteCsvValidator(
                uploaded_file=file,
                schema=SITE_SCHEMA,
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

        # 4. Build response

        # -----------------------------------------------------

        response_data = report.to_dict()

        # -----------------------------------------------------

        # 5. Cache successful validation

        # -----------------------------------------------------

        if report.success:

            validation_id = ValidationCache.save(
                report=report,
                filiale=filiale,
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


class ImportSiteView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.site"

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

        # The import writes into the affiliate recorded at validation

        # time: the user must be allowed to write into it.

        _validation_payload = ValidationCache.get(validation_id)

        _import_filiale = (_validation_payload or {}).get("filiale")

        if _import_filiale and not can_access_filiale(

            request.user, _import_filiale

        ):

            return Response(
                {
                    "success": False,
                    "message": "Accès refusé à cette filiale.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # -----------------------------------------------------

# 2. Import validated rows

        # -----------------------------------------------------

        try:

            importer = SiteCsvImporter(
                validation_id=validation_id,
                user=request.user,
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

        except Exception as exc:

            views_logger.error(
                f"{self.__class__.__name__} import failed: {exc}",
                exc_info=True,
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "Une erreur inattendue est survenue " "pendant l'import."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -----------------------------------------------------

        # 3. Successful import

        # -----------------------------------------------------

        # -----------------------------------------------------

        # Notify admins about pending imports

        # -----------------------------------------------------

        try:

            notify_pending_import(
                request=request,
                result=result,
                module_name="Site",
            )

        except Exception as e:

            import logging

            logger = logging.getLogger(__name__)

            logger.error(f"notify_pending_import failed: {e}", exc_info=True)

        return Response(
            {
                **result,
                "message": "Import Terminé avec Succès.",
            },
            status=status.HTTP_201_CREATED,
        )


class DashboardAPIView(PagePermissionRequiredMixin, APIView):
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

    permission_required = "analyse.dashboard"

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


class DashboardV2BaseAPIView(PagePermissionRequiredMixin, APIView):
    permission_required = ("analyse.dashboard",)

    def get_filters(self):
        return {
            "code_filiale": self.request.query_params.get("code_filiale"),
            "date_debut": self.request.query_params.get("date_debut"),
            "date_fin": self.request.query_params.get("date_fin"),
            "code_famille": self.request.query_params.get("code_famille"),
        }

    def get_niveau(self):
        return self.request.query_params.get("niveau", "engin")

    def get_db_aliases(self):
        code_filiale = self.request.query_params.get("code_filiale")
        if code_filiale:
            return [filiale_db_name(code_filiale)]
        if can_access_all_filiales(self.request.user):
            return [filiale_db_name(code) for code in settings.FILIALE_DATABASES]
        return [None]


class DashboardV2OverviewAPIView(DashboardV2BaseAPIView):
    """



    GET /api/dashboard-v2/overview/







    Returns `{ globalKpis, maintenanceKpis, financialKpis }`. The `niveau`



    query param is ignored on purpose (the overview is fleet-scoped).



    """

    def get(self, request):

        f = self.get_filters()
        aliases = self.get_db_aliases()
        if len(aliases) == 1:
            data = DashboardV2Service.get_overview(
                code_filiale=f["code_filiale"],
                date_debut=f["date_debut"],
                date_fin=f["date_fin"],
                code_famille=f["code_famille"],
                using=aliases[0],
            )
            return Response(data)

        # Cross-filiale merge: query every affiliate database and merge the
        # per-filiale results in Python. The FailClosedDatabaseRouter has no
        # filiale to route to when ``code_filiale`` is None and the user is an
        # admin, so without this loop every query falls back to the central
        # ``default`` database — which has empty affiliate-scoped tables.
        global_kpis_list = []
        maintenance_kpis_list = []
        financial_kpis_list = []
        filiale_distribution_list = []
        for alias in aliases:
            overview = DashboardV2Service.get_overview(
                code_filiale=None,
                date_debut=f["date_debut"],
                date_fin=f["date_fin"],
                code_famille=f["code_famille"],
                using=alias,
            )
            global_kpis_list.append(overview["globalKpis"])
            maintenance_kpis_list.append(overview["maintenanceKpis"])
            financial_kpis_list.append(overview["financialKpis"])
            filiale_distribution_list.append(overview["filialeDistribution"])

        data = {
            "globalKpis": DashboardV2Service._merge_global_kpis(global_kpis_list),
            "maintenanceKpis": DashboardV2Service._merge_maintenance_kpis(maintenance_kpis_list),
            "financialKpis": DashboardV2Service._merge_financial_kpis(financial_kpis_list),
            "filialeDistribution": DashboardV2Service._merge_filiale_distribution(
                filiale_distribution_list
            ),
        }

        return Response(data)


class DashboardV2SituationAPIView(DashboardV2BaseAPIView):
    """



    GET /api/dashboard-v2/situation/







    Returns `{ situationDistribution, pointageEvolution, familleDistribution }`.



    The `niveau` query param is ignored on purpose.



    """

    def get(self, request):

        f = self.get_filters()
        aliases = self.get_db_aliases()
        if len(aliases) == 1:
            data = DashboardV2Service.get_situation(
                code_filiale=f["code_filiale"],
                date_debut=f["date_debut"],
                date_fin=f["date_fin"],
                code_famille=f["code_famille"],
                using=aliases[0],
            )
            return Response(data)

        # Cross-filiale merge: query every affiliate database and merge the
        # per-filiale results in Python.
        situation_distributions = []
        pointage_evolutions = []
        famille_distributions = []
        for alias in aliases:
            situation = DashboardV2Service.get_situation(
                code_filiale=None,
                date_debut=f["date_debut"],
                date_fin=f["date_fin"],
                code_famille=f["code_famille"],
                using=alias,
            )
            situation_distributions.append(situation["situationDistribution"])
            pointage_evolutions.append(situation["pointageEvolution"])
            famille_distributions.append(situation["familleDistribution"])

        data = {
            "situationDistribution": DashboardV2Service._merge_situation_distribution(
                situation_distributions
            ),
            "pointageEvolution": DashboardV2Service._merge_evolution(pointage_evolutions),
            "familleDistribution": DashboardV2Service._merge_famille_distribution(
                famille_distributions
            ),
        }

        return Response(data)


class DashboardV2DisponibiliteAPIView(DashboardV2BaseAPIView):
    """



    GET /api/dashboard-v2/disponibilite/







    Query params: code_filiale, date_debut, date_fin, code_famille, niveau.



    Returns `{ evolution, breakdown }`.



    """

    def get(self, request):

        f = self.get_filters()
        aliases = self.get_db_aliases()
        if len(aliases) == 1:
            data = DashboardV2Service.get_disponibilite(
                code_filiale=f["code_filiale"],
                date_debut=f["date_debut"],
                date_fin=f["date_fin"],
                code_famille=f["code_famille"],
                niveau=self.get_niveau(),
                using=aliases[0],
            )
            return Response(data)

        # Cross-filiale merge: query every affiliate database and merge the
        # per-filiale results in Python.
        evolutions = []
        breakdowns = []
        for alias in aliases:
            result = DashboardV2Service.get_disponibilite(
                code_filiale=None,
                date_debut=f["date_debut"],
                date_fin=f["date_fin"],
                code_famille=f["code_famille"],
                niveau=self.get_niveau(),
                using=alias,
            )
            evolutions.append(result["evolution"])
            breakdowns.append(result["breakdown"])

        data = {
            "evolution": DashboardV2Service._merge_evolution(evolutions),
            "breakdown": DashboardV2Service._merge_breakdown(breakdowns),
        }

        return Response(data)


class DashboardV2MaintenanceAPIView(DashboardV2BaseAPIView):
    """



    GET /api/dashboard-v2/maintenance/







    Query params: code_filiale, date_debut, date_fin, code_famille, niveau.



    Returns `{ mtbf, mttr, coutPanne }`, each `{ evolution, breakdown }`.



    """

    def get(self, request):

        f = self.get_filters()
        aliases = self.get_db_aliases()
        if len(aliases) == 1:
            data = DashboardV2Service.get_maintenance(
                code_filiale=f["code_filiale"],
                date_debut=f["date_debut"],
                date_fin=f["date_fin"],
                code_famille=f["code_famille"],
                niveau=self.get_niveau(),
                using=aliases[0],
            )
            return Response(data)

        # Cross-filiale merge: query every affiliate database and merge the
        # per-filiale results in Python.
        mtbf_evolutions = []
        mtbf_breakdowns = []
        mttr_evolutions = []
        mttr_breakdowns = []
        cout_panne_evolutions = []
        cout_panne_breakdowns = []
        for alias in aliases:
            result = DashboardV2Service.get_maintenance(
                code_filiale=None,
                date_debut=f["date_debut"],
                date_fin=f["date_fin"],
                code_famille=f["code_famille"],
                niveau=self.get_niveau(),
                using=alias,
            )
            mtbf_evolutions.append(result["mtbf"]["evolution"])
            mtbf_breakdowns.append(result["mtbf"]["breakdown"])
            mttr_evolutions.append(result["mttr"]["evolution"])
            mttr_breakdowns.append(result["mttr"]["breakdown"])
            cout_panne_evolutions.append(result["coutPanne"]["evolution"])
            cout_panne_breakdowns.append(result["coutPanne"]["breakdown"])

        data = {
            "mtbf": {
                "evolution": DashboardV2Service._merge_evolution(mtbf_evolutions),
                "breakdown": DashboardV2Service._merge_breakdown(mtbf_breakdowns),
            },
            "mttr": {
                "evolution": DashboardV2Service._merge_evolution(mttr_evolutions),
                "breakdown": DashboardV2Service._merge_breakdown(mttr_breakdowns),
            },
            "coutPanne": {
                "evolution": DashboardV2Service._merge_evolution(cout_panne_evolutions),
                "breakdown": DashboardV2Service._merge_breakdown(cout_panne_breakdowns),
            },
        }

        return Response(data)


class DashboardV2RendementAPIView(DashboardV2BaseAPIView):
    """



    GET /api/dashboard-v2/rendement/







    Query params: code_filiale, date_debut, date_fin, code_famille, niveau.



    Returns `{ pointageEvolution, rendementEvolution, breakdown }`.



    """

    def get(self, request):

        f = self.get_filters()
        aliases = self.get_db_aliases()
        if len(aliases) == 1:
            data = DashboardV2Service.get_rendement(
                code_filiale=f["code_filiale"],
                date_debut=f["date_debut"],
                date_fin=f["date_fin"],
                code_famille=f["code_famille"],
                niveau=self.get_niveau(),
                using=aliases[0],
            )
            return Response(data)

        # Cross-filiale merge: query every affiliate database and merge the
        # per-filiale results in Python.
        pointage_evolutions = []
        rendement_evolutions = []
        breakdowns = []
        for alias in aliases:
            result = DashboardV2Service.get_rendement(
                code_filiale=None,
                date_debut=f["date_debut"],
                date_fin=f["date_fin"],
                code_famille=f["code_famille"],
                niveau=self.get_niveau(),
                using=alias,
            )
            pointage_evolutions.append(result["pointageEvolution"])
            rendement_evolutions.append(result["rendementEvolution"])
            breakdowns.append(result["breakdown"])

        data = {
            "pointageEvolution": DashboardV2Service._merge_evolution(pointage_evolutions),
            "rendementEvolution": DashboardV2Service._merge_evolution(rendement_evolutions),
            "breakdown": DashboardV2Service._merge_breakdown(breakdowns),
        }

        return Response(data)


class DashboardV2FinancesAPIView(DashboardV2BaseAPIView):
    """



    GET /api/dashboard-v2/finances/







    Query params: code_filiale, date_debut, date_fin, code_famille, niveau.



    Returns `{ caLocationInterne, rentabilite, tauxAffectation, tauxAffectationGlobal,



    tauxUtilisation, tauxChomage }`.



    """

    def get(self, request):

        f = self.get_filters()
        aliases = self.get_db_aliases()
        if len(aliases) == 1:
            data = DashboardV2Service.get_finances(
                code_filiale=f["code_filiale"],
                date_debut=f["date_debut"],
                date_fin=f["date_fin"],
                code_famille=f["code_famille"],
                niveau=self.get_niveau(),
                using=aliases[0],
            )
            return Response(data)

        # Cross-filiale merge: query every affiliate database and merge the
        # per-filiale results in Python. The rentabilite ranking is cached per
        # (filiale, date, famille) so it is re-queried per alias; the cache key
        # already includes ``code_filiale or "all"`` which is ``None`` here, so
        # each alias's ranking is cached independently and merged by code.
        ca_evolutions = []
        ca_breakdowns = []
        taux_utilisation_evolutions = []
        taux_utilisation_breakdowns = []
        taux_chomage_evolutions = []
        taux_chomage_breakdowns = []
        rentabilite_evolutions = []
        rentabilite_rankings = []
        taux_affectation_evolutions = []
        taux_affectation_breakdowns = []
        taux_affectation_globals = []
        for alias in aliases:
            result = DashboardV2Service.get_finances(
                code_filiale=None,
                date_debut=f["date_debut"],
                date_fin=f["date_fin"],
                code_famille=f["code_famille"],
                niveau=self.get_niveau(),
                using=alias,
            )
            ca_evolutions.append(result["caLocationInterne"]["evolution"])
            ca_breakdowns.append(result["caLocationInterne"]["breakdown"])
            taux_utilisation_evolutions.append(result["tauxUtilisation"]["evolution"])
            taux_utilisation_breakdowns.append(result["tauxUtilisation"]["breakdown"])
            taux_chomage_evolutions.append(result["tauxChomage"]["evolution"])
            taux_chomage_breakdowns.append(result["tauxChomage"]["breakdown"])
            rentabilite_evolutions.append(result["rentabilite"]["evolution"])
            rentabilite_rankings.append(result["rentabilite"]["ranking"])
            taux_affectation_evolutions.append(result["tauxAffectation"]["evolution"])
            taux_affectation_breakdowns.append(result["tauxAffectation"]["breakdown"])
            taux_affectation_globals.append(result["tauxAffectationGlobal"])

        # Merge taux_affectation_global: sum parc_total and engins_affectes, then
        # recompute the rate from the merged totals (the frontend must never
        # sum a niveau-dependent breakdown to derive the global rate).
        merged_parc_total = sum(
            float(g.get("parc_total", 0) or 0) for g in taux_affectation_globals
        )
        merged_engins_affectes = sum(
            float(g.get("engins_affectes", 0) or 0) for g in taux_affectation_globals
        )
        taux_affectation_global = {
            "parc_total": merged_parc_total,
            "engins_affectes": merged_engins_affectes,
            "taux_affectation": round(
                (merged_engins_affectes / merged_parc_total * 100)
                if merged_parc_total
                else 0.0,
                1,
            ),
        }

        data = {
            "caLocationInterne": {
                "evolution": DashboardV2Service._merge_evolution(ca_evolutions),
                "breakdown": DashboardV2Service._merge_breakdown(ca_breakdowns),
            },
            "rentabilite": {
                "evolution": DashboardV2Service._merge_evolution(rentabilite_evolutions),
                "ranking": DashboardV2Service._merge_rentabilite_ranking(
                    rentabilite_rankings
                ),
            },
            "tauxAffectation": {
                "evolution": DashboardV2Service._merge_evolution(taux_affectation_evolutions),
                "breakdown": DashboardV2Service._merge_breakdown(taux_affectation_breakdowns),
                "global": taux_affectation_global,
            },
            "tauxAffectationGlobal": taux_affectation_global,
            "tauxUtilisation": {
                "evolution": DashboardV2Service._merge_evolution(taux_utilisation_evolutions),
                "breakdown": DashboardV2Service._merge_breakdown(taux_utilisation_breakdowns),
            },
            "tauxChomage": {
                "evolution": DashboardV2Service._merge_evolution(taux_chomage_evolutions),
                "breakdown": DashboardV2Service._merge_breakdown(taux_chomage_breakdowns),
            },
        }

        return Response(data)


class DashboardV2FilialesAPIView(DashboardV2BaseAPIView):
    """



    GET /api/dashboard-v2/filiales/







    Returns `[{ value, label }]` of the active subsidiaries.



    """

    def get(self, request):

        codes = get_allowed_filiale_codes(request.user)
        return Response(DashboardV2Service.get_filiales(codes))


class DashboardV2FamillesAPIView(DashboardV2BaseAPIView):
    """



    GET /api/dashboard-v2/familles/







    Returns `[{ value, label }]` of the active material families.



    """

    def get(self, request):

        return Response(DashboardV2Service.get_familles())


class DashboardV2FilialeStatsAPIView(DashboardV2BaseAPIView):
    """



    GET /api/dashboard-v2/filiale-stats/







    Returns per-filiale aggregation of parc, affectations, heures service



    and pointages, honoring the optional code_filiale / date / famille filters.



    Grouped on the material's group (`code_materiel__code_filiale_g`); a



    `code_filiale` filter collapses the list to a single row.



    """

    def get(self, request):

        f = self.get_filters()
        aliases = self.get_db_aliases()
        if len(aliases) == 1:
            return Response(
                DashboardV2Service.get_filiale_stats(
                    code_filiale=f["code_filiale"],
                    date_debut=f["date_debut"],
                    date_fin=f["date_fin"],
                    code_famille=f["code_famille"],
                    using=aliases[0],
                )
            )

        # Cross-filiale merge: query every affiliate database and merge the
        # per-filiale results in Python. Each alias returns per-filiale stats
        # grouped by code_filiale_g, so the merge is keyed by code_filiale.
        stats_list = []
        for alias in aliases:
            stats_list.append(
                DashboardV2Service.get_filiale_stats(
                    code_filiale=None,
                    date_debut=f["date_debut"],
                    date_fin=f["date_fin"],
                    code_famille=f["code_famille"],
                    using=alias,
                )
            )

        return Response(DashboardV2Service._merge_filiale_stats(stats_list))


class CurrentUserView(PagePermissionRequiredMixin, APIView):

    permission_required = None

    def get(self, request):

        profile = getattr(request.user, "profile", None)

        permissions_list = profile.permissions if profile else []

        profile_filiale = getattr(profile, "filiale", None) if profile else None
        filiale_code = profile_filiale.code_filiale if profile_filiale else None

        from django.conf import settings

        from api.permissions import can_access_all_filiales

        if can_access_all_filiales(request.user):

            accessible_databases = [

                filiale_db_name(code) for code in settings.FILIALE_DATABASES

            ]

        elif filiale_code:

            accessible_databases = [filiale_db_name(filiale_code)]

        else:

            accessible_databases = []

        data = {
            "id": request.user.id,
            "username": request.user.username,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "email": request.user.email,
            "is_active": request.user.is_active,
            "is_superuser": request.user.is_superuser,
            "permissions": permissions_list,

            "can_access_all_filiales": can_access_all_filiales(request.user),
            "filiale": filiale_code,

            "accessible_databases": accessible_databases,
        }

        return Response(data)


class ExternalServiceClientViewSet(JournalisedModelViewSet):
    queryset = ExternalServiceClient.objects.all().order_by("-created_at")
    permission_required = "administration.users"
    search_fields = ["name", "client_id"]
    journal_module = JournalModules.PARAMETRAGE
    journal_objet_type = "ExternalServiceClient"

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ExternalServiceClientWriteSerializer
        return ExternalServiceClientSerializer

    def perform_create(self, serializer):
        instance = serializer.save()
        secret = serializer.context.get("client_secret")
        if secret:
            setattr(self.request, "_client_secret_plain", secret)
        super().perform_create(serializer)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        data = ExternalServiceClientSerializer(instance=serializer.instance, context={"request": request}).data
        secret = getattr(request, "_client_secret_plain", None) or serializer.context.get("client_secret")
        if secret:
            data["client_secret"] = secret
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        data = ExternalServiceClientSerializer(instance=instance, context={"request": request}).data
        secret = serializer.context.get("client_secret")
        if secret:
            data["client_secret"] = secret
        return Response(data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


class UserViewSet(JournalisedModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    journal_module = JournalModules.UTILISATEUR
    journal_objet_type = "User"
    permission_required = "administration.users"
    search_fields = ["username", "first_name", "last_name", "email"]

    def get_permissions(self):

        if self.action in ("me", "preferences", "change_password"):

            return [permissions.IsAuthenticated()]

        return super().get_permissions()

    def perform_create(self, serializer):

        password = serializer.validated_data.get("password")

        user = serializer.save()

        if password:

            user.set_password(password)

            user.save()

        self._apply_profile_filiale(user)

        log_action(
            user=self.request.user,
            action=JournalActions.CREATE,
            module=JournalModules.UTILISATEUR,
            objet_type="User",
            objet_id=user.pk,
            nouvelle_valeur=serialize_for_journal(user, UserSerializer),
            request=self.request,
            description=f"Création de User",
        )

    def _apply_profile_filiale(self, user):
        """Persist the optional filiale selection on the user's profile."""
        raw = self.request.data.get("filiale")
        if raw is None:
            code = None
        else:
            code = str(raw).strip() or None
        filiale = Filiale.objects.filter(code_filiale=code).first() if code else None
        profile = UserProfile.objects.get_or_create(user=user)[0]
        profile.filiale = filiale
        profile.save()

    def perform_update(self, serializer):

        user = serializer.instance

        old_data = serialize_for_journal(user, UserSerializer)

        password = serializer.validated_data.get("password")

        user = serializer.save()

        if password:

            user.set_password(password)

            user.save()

        if "filiale" in self.request.data:

            self._apply_profile_filiale(user)

        new_data = serialize_for_journal(user, UserSerializer)

        log_action(
            user=self.request.user,
            action=JournalActions.UPDATE,
            module=JournalModules.UTILISATEUR,
            objet_type="User",
            objet_id=user.pk,
            ancienne_valeur=old_data,
            nouvelle_valeur=new_data,
            request=self.request,
            description=f"Modification de User",
        )

    def perform_destroy(self, instance):

        old_data = serialize_for_journal(instance, UserSerializer)

        super().perform_destroy(instance)

        log_action(
            user=self.request.user,
            action=JournalActions.DELETE,
            module=JournalModules.UTILISATEUR,
            objet_type="User",
            objet_id=instance.pk,
            ancienne_valeur=old_data,
            request=self.request,
            description=f"Suppression de User",
        )

    @action(detail=True, methods=["get", "patch"], url_path="permissions")
    def permissions(self, request, pk=None):

        user = self.get_object()

        profile, _ = UserProfile.objects.get_or_create(user=user)

        if request.method == "PATCH":

            old_permissions = list(profile.permissions) if profile.permissions else []

            serializer = UserProfileSerializer(profile, data=request.data, partial=True)

            serializer.is_valid(raise_exception=True)

            serializer.save()

            profile = serializer.instance

            log_action(
                user=self.request.user,
                action=JournalActions.UPDATE,
                module=JournalModules.UTILISATEUR,
                objet_type="UserProfile",
                objet_id=profile.pk,
                ancienne_valeur={"permissions": old_permissions},
                nouvelle_valeur={"permissions": profile.permissions},
                request=self.request,
                description=f"Modification des droits d'accès pour User",
            )

        return Response(UserProfileSerializer(profile).data)

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):

        profile = getattr(request.user, "profile", None)

        permissions_list = profile.permissions if profile else []

        profile_filiale = getattr(profile, "filiale", None) if profile else None
        filiale_code = profile_filiale.code_filiale if profile_filiale else None

        from django.conf import settings
        from api.permissions import can_access_all_filiales
        from .multidb import filiale_db_name

        if can_access_all_filiales(request.user):

            accessible_databases = [

                filiale_db_name(code) for code in settings.FILIALE_DATABASES

            ]

        elif filiale_code:

            accessible_databases = [filiale_db_name(filiale_code)]

        else:

            accessible_databases = []

        data = {
            "id": request.user.id,
            "username": request.user.username,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "email": request.user.email,
            "is_active": request.user.is_active,
            "is_superuser": request.user.is_superuser,
            "permissions": permissions_list,

            "can_access_all_filiales": can_access_all_filiales(request.user),
            "filiale": filiale_code,

            "accessible_databases": accessible_databases,
        }

        return Response(data)

    @action(detail=False, methods=["get", "patch"], url_path="preferences")
    def preferences(self, request):

        profile, _ = UserProfile.objects.get_or_create(user=request.user)

        if request.method == "GET":

            serializer = UserPreferencesSerializer(profile)

            return Response(serializer.data)

        serializer = UserPreferencesSerializer(profile, data=request.data, partial=True)

        serializer.is_valid(raise_exception=True)

        serializer.save()

        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="change_password")
    def change_password(self, request):

        user = request.user

        current_password = request.data.get("current_password")

        new_password = request.data.get("new_password")

        if not current_password or not new_password:

            return Response(
                {
                    "detail": "Le mot de passe actuel et le nouveau mot de passe sont obligatoires."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.check_password(current_password):

            return Response(
                {"current_password": ["Mot de passe actuel incorrect."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if current_password == new_password:

            return Response(
                {
                    "new_password": [
                        "Le nouveau mot de passe doit être différent de l'ancien."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            validate_password(new_password, user=user)

        except Exception as exc:

            return Response(
                {"new_password": [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)

        user.save()

        log_action(
            user=request.user,
            action=JournalActions.UPDATE,
            module=JournalModules.UTILISATEUR,
            objet_type="User",
            objet_id=user.pk,
            description=f"Changement de mot de passe pour User",
            request=request,
        )

        return Response(
            {
                "detail": "Mot de passe modifié avec succès."
            }
        )

    @action(detail=True, methods=["post"], url_path="set_password")
    def set_password(self, request, pk=None):

        user = self.get_object()

        password = request.data.get("password")

        if not password:

            return Response(
                {"message": "Le mot de passe est obligatoire."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)

        user.save()

        log_action(
            user=self.request.user,
            action=JournalActions.UPDATE,
            module=JournalModules.UTILISATEUR,
            objet_type="User",
            objet_id=user.pk,
            description=f"Changement de mot de passe pour User",
            request=self.request,
        )

        return Response(
            {
                "message": "Mot de passe mis à jour."
            }
        )


def notify_pending_import(request, result, module_name, batch_id=None, count=None):

    import logging
    logger = logging.getLogger(__name__)

    try:

        from django.contrib.auth import get_user_model

        User = get_user_model()

        logger.info(f"notify_pending_import called: module_name={module_name}, result_keys={list(result.keys()) if isinstance(result, dict) else 'not dict'}")

        if batch_id is None:

            batch_id = (
                result.get("import_batch_id") if isinstance(result, dict) else None
            )

        if count is None:

            if isinstance(result, dict):

                count = result.get("imported_rows", 0)

                if count == 0:

                    count = result.get("imported_affectations", 0) + result.get(
                        "imported_situations", 0
                    )

            else:

                count = 0

        # Skip notification if no records were imported
        if count == 0:
            logger.info(f"notify_pending_import: count=0, skipping notification for {module_name}")
            return

        logger.info(f"notify_pending_import: batch_id={batch_id}, count={count}")

        admins = User.objects.filter(is_superuser=True).distinct()

        logger.info(f"notify_pending_import: found {admins.count()} superusers")

        title = f"Import en attente: {module_name}"

        message = f"{count} enregistrement(s) importé(s) en attente de confirmation (lot {str(batch_id)[:8] if batch_id else ''})."

        importer = request.user if request.user.is_authenticated else None

        # Build the list of recipients: admins plus the importing user (if not already an admin)
        recipients = list(admins)
        if importer and not admins.filter(id=importer.id).exists():
            recipients.append(importer)

        for a in recipients:

            Notification.objects.create(
                recipient=a,
                title=title,
                message=message,
                type="PENDING_IMPORT",
                related_object_type=module_name,
                related_object_id=str(batch_id) if batch_id else None,
                created_by=importer,
            )
            logger.info(f"notify_pending_import: created notification for {a.username}")

    except Exception as e:

        logger.error(f"notify_pending_import failed: {e}", exc_info=True)
        pass


class PendingListView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.pointage"  # broad; adjust as needed

    def get(self, request):

        from django.contrib.auth import get_user_model

        from django.apps import apps

        from collections import defaultdict

        from django.conf import settings

        batch_id = request.query_params.get("batch_id")

        model = request.query_params.get("model")

        # Models that support import batches and status

        model_configs = [
            ("pointage", Pointage, "gestion.pointages"),
            ("grand_materiel", Grand_Materiel, "gestion.materiels"),
            ("affectation_materiel", Affectation_Materiel, "gestion.affectations"),
            ("situation_materiel", Situation_Materiel, "gestion.situations"),
            ("site", Site, "gestion.sites"),
            ("famille_materiel", Famille_Materiel, "gestion.familles_materiel"),
            (
                "sous_famille_materiel",
                Sous_Famille_Materiel,
                "gestion.sous_familles_materiel",
            ),
            ("marque_materiel", Marque_Materiel, "gestion.marques_materiel"),
            ("type_marque", Type_Marque, "gestion.types_marque"),
            ("categorie_gm", Categorie_GM, "gestion.categories_gm"),
            ("regularisation_gm", Regularisation_GM, "gestion.regularisations_gm"),
        ]

        # Determine which filiale databases to scan. Admin queries every
        # filiale DB separately and merges in Python.
        filiale_dbs = [
            filiale_db_name(code) for code in settings.FILIALE_DATABASES
        ]

        result = []

        if batch_id:

            # Return details for a specific batch: find the filiale DB that
            # owns the batch, then query only that database.

            owner_db = find_filiale_db_for_batch(batch_id)

            if owner_db is None:

                return Response({"batch_id": batch_id, "models": []})

            dbs_to_query = [owner_db]

            for model_key, ModelClass, perm in model_configs:

                if model and model != model_key:

                    continue

                try:

                    qs = (
                        ModelClass.objects.using(dbs_to_query[0])
                        .filter(status="PENDING", import_batch_id=batch_id)
                    )

                    items = []

                    for obj in qs[:100]:  # limit preview

                        # Helper to extract string value from field (handle ForeignKey)
                        def get_field_value(obj, *field_names):
                            for field_name in field_names:
                                val = getattr(obj, field_name, None)
                                if val is not None:
                                    # If it's a model instance (ForeignKey), get its string representation or pk
                                    if hasattr(val, "_meta"):  # Django model instance
                                        return str(val)
                                    return val
                            return None

                        items.append(
                            {
                                "id": obj.id,
                                "code": get_field_value(
                                    obj, "code", "code_materiel", "code_affectation"
                                ),
                                "designation": get_field_value(
                                    obj, "designation", "libelle"
                                ),
                                "created_at": (
                                    obj.created_at.isoformat()
                                    if hasattr(obj, "created_at") and obj.created_at
                                    else None
                                ),
                            }
                        )

                    if qs.exists() or (model and model == model_key):

                        result.append(
                            {
                                "model": model_key,
                                "count": qs.count(),
                                "items": items,
                            }
                        )

                except Exception:

                    continue

            return Response({"batch_id": batch_id, "models": result})

        # Group by batch_id across all filiale databases.

        batches = defaultdict(
            lambda: {"models": defaultdict(int), "created_at": None, "module": None}
        )

        for model_key, ModelClass, perm in model_configs:

            for db in filiale_dbs:

                try:

                    qs = ModelClass.objects.using(db).filter(
                        status="PENDING"
                    ).exclude(import_batch_id__isnull=True)

                    for obj in (
                        qs.values("import_batch_id")
                        .annotate(c=Count("id"))
                        .order_by()
                    ):

                        bid = obj["import_batch_id"]

                        batches[bid]["models"][model_key] += obj["c"]

                except Exception:

                    continue

        # Try to get representative created_at and module from notifications

        for bid, data in batches.items():

            try:

                notif = (
                    Notification.objects.filter(
                        related_object_id=str(bid), type="PENDING_IMPORT"
                    )
                    .order_by("-created_at")
                    .first()
                )

                if notif:

                    data["created_at"] = (
                        notif.created_at.isoformat() if notif.created_at else None
                    )

                    data["module"] = notif.related_object_type

                    data["title"] = notif.title

            except Exception:

                pass

        batches_list = []

        for bid, data in batches.items():

            batches_list.append(
                {
                    "batch_id": bid,
                    "module": data.get("module"),
                    "title": data.get("title"),
                    "created_at": data.get("created_at"),
                    "models": dict(data["models"]),
                    "total": sum(data["models"].values()),
                }
            )

        batches_list.sort(key=lambda x: x.get("created_at") or "", reverse=True)

        return Response({"batches": batches_list})


class ConfirmPendingView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.pointage"

    def post(self, request):

        from django.utils import timezone

        user = request.user

        if not getattr(user, "is_superuser", False):

            return Response(
                {
                    "success": False,
                    "message": "Non autorisÃÂ©",
                },
                status=403,
            )

        model_name = request.data.get("model")

        ids = request.data.get("ids") or []

        batch_id = request.data.get("batch_id")

        model_map = {
            "pointage": Pointage,
            "grand_materiel": Grand_Materiel,
            "affectation_materiel": Affectation_Materiel,
            "situation_materiel": Situation_Materiel,
            "site": Site,
            "famille_materiel": Famille_Materiel,
            "sous_famille_materiel": Sous_Famille_Materiel,
            "marque_materiel": Marque_Materiel,
            "type_marque": Type_Marque,
            "categorie_gm": Categorie_GM,
            "regularisation_gm": Regularisation_GM,
        }

        if model_name not in model_map:

            return Response(
                {
                    "success": False,
                    "message": "ModÃÂ¨le non pris en charge",
                },
                status=400,
            )

        ModelClass = model_map[model_name]

        if batch_id:

            # A batch belongs to a single filiale database. Resolve it and
            # route all writes to that database.
            db = find_filiale_db_for_batch(batch_id)

            if db is None:

                return Response(
                    {
                        "success": False,
                        "message": "Aucun lot en attente trouvÃÂ© pour ce batch_id.",
                    },
                    status=404,
                )

            with transaction.atomic(using=db):

                qs = (
                    ModelClass.objects.using(db)
                    .select_for_update()
                    .filter(status="PENDING", import_batch_id=batch_id)
                )

                if ids:

                    qs = qs.filter(id__in=ids)

                updated = qs.update(
                    status="CONFIRMED", confirmed_by=user, confirmed_at=timezone.now()
                )

        else:

            # Single-DB confirmation scoped to the current request's filiale.

            from .multidb import get_current_filiale, filiale_db_name

            from django.conf import settings

            code = get_current_filiale()

            if not code:

                return Response(
                    {
                        "success": False,
                        "message": "Aucune filiale rÃÂ©solue pour cette requÃÂate.",
                    },
                    status=400,
                )

            db = filiale_db_name(code)

            if db not in settings.DATABASES:

                return Response(
                    {
                        "success": False,
                        "message": f"Base de donnÃÂes filiale '{db}' introuvable.",
                    },
                    status=400,
                )

            with transaction.atomic(using=db):

                qs = (
                    ModelClass.objects.using(db)
                    .select_for_update()
                    .filter(status="PENDING")
                )

                if ids:

                    qs = qs.filter(id__in=ids)

                updated = qs.update(
                    status="CONFIRMED", confirmed_by=user, confirmed_at=timezone.now()
                )

        return Response({"success": True, "updated": updated})


# Maximum number of validation errors returned to the client by the bulk
# confirmation endpoint.  A batch can hold tens of thousands of rows, so the
# full list is logged server-side instead of being sent over the wire.

MAX_BULK_CONFIRM_ERRORS = 50


class BulkConfirmPendingView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.pointage"

    def post(self, request):

        import logging

        logger = logging.getLogger(__name__)

        from django.utils import timezone

        user = request.user

        if not getattr(user, "is_superuser", False):

            return Response(
                {
                    "success": False,
                    "message": "Non autorisÃÂ©",
                },
                status=403,
            )

        batch_id = request.data.get("batch_id")

        if not batch_id:

            return Response(
                {"success": False, "message": "batch_id requis"}, status=400
            )

        # Resolve the single filiale database that owns this batch.

        db = find_filiale_db_for_batch(batch_id)

        if db is None:

            return Response(
                {
                    "success": False,
                    "message": "Aucun lot en attente trouvÃÂ© pour ce batch_id.",
                },
                status=404,
            )

        model_map = {
            "pointage": Pointage,
            "grand_materiel": Grand_Materiel,
            "affectation_materiel": Affectation_Materiel,
            "situation_materiel": Situation_Materiel,
            "site": Site,
            "famille_materiel": Famille_Materiel,
            "sous_famille_materiel": Sous_Famille_Materiel,
            "marque_materiel": Marque_Materiel,
            "type_marque": Type_Marque,
            "categorie_gm": Categorie_GM,
            "regularisation_gm": Regularisation_GM,
        }

        total_updated = 0

        errors = []

        # A batch belongs to one affiliate, which is not necessarily the
        # affiliate of the administrator confirming it.  Django resolves the
        # database of the foreign-key and unique checks performed by
        # ``full_clean()`` through the router, which always answers with the
        # request-scoped affiliate.  Without pinning the routing to the
        # affiliate that owns the batch, every row would be validated
        # against the wrong database and reported as invalid.

        affiliate_code = filiale_code_for_db(db)

        with affiliate_routing(affiliate_code):

            with transaction.atomic(using=db):

                # Validate every pending row of the batch first, so that
                # nothing is confirmed when a single row is invalid.

                for model_name, ModelClass in model_map.items():

                    try:

                        qs = (
                            ModelClass.objects.using(db)
                            .select_for_update()
                            .filter(status="PENDING", import_batch_id=batch_id)
                        )

                        for obj in qs:

                            try:

                                obj.full_clean()

                            except Exception as e:

                                errors.append(f"{model_name} {obj.id}: {str(e)}")

                    except Exception as e:

                        errors.append(f"{model_name}: {str(e)}")

                if not errors:

                    for model_name, ModelClass in model_map.items():

                        try:

                            updated = (
                                ModelClass.objects.using(db)
                                .filter(status="PENDING", import_batch_id=batch_id)
                                .update(
                                    status="CONFIRMED",
                                    confirmed_by=user,
                                    confirmed_at=timezone.now(),
                                )
                            )

                            total_updated += updated

                        except Exception as e:

                            errors.append(f"{model_name}: {str(e)}")

        if errors:

            logger.error(
                "Bulk confirmation of batch %s failed: %d validation error(s). "
                "First errors: %s",
                batch_id,
                len(errors),
                errors[:20],
            )

            return Response(
                {
                    "success": False,
                    "message": "Erreurs de validation",
                    "errors": errors[:MAX_BULK_CONFIRM_ERRORS],
                    "error_count": len(errors),
                },
                status=400,
            )

        # Update pending notifications for this batch to IMPORT_CONFIRMED
        if batch_id and total_updated > 0:

            try:

                from .models.notification import Notification as _Notification

                confirm_time = timezone.now()

                _Notification.objects.filter(
                    type="PENDING_IMPORT",
                    related_object_id=str(batch_id),
                ).update(
                    type="IMPORT_CONFIRMED",
                    title=f"Import confirmé: lot {str(batch_id)[:8]}",
                    message=f"{total_updated} enregistrement(s) importé(s) (lot {str(batch_id)[:8] if batch_id else ''}) ont été confirmés par l'administrateur.",
                    is_read=False,
                    import_datetime=None,
                    record_count=total_updated,
                    rejection_reason=None,
                    rejection_datetime=None,
                )

                # Track the confirmation datetime by updating each notification individually
                confirm_qs = _Notification.objects.filter(
                    type="IMPORT_CONFIRMED",
                    related_object_id=str(batch_id),
                )
                for notif in confirm_qs:
                    notif.confirmation_datetime = confirm_time
                    notif.save(update_fields=["confirmation_datetime"])

            except Exception as e:

                logger.error(
                    f"Failed to update pending notifications to IMPORT_CONFIRMED: {e}",
                    exc_info=True,
                )

        return Response({"success": True, "updated": total_updated})


class RejectPendingView(PagePermissionRequiredMixin, APIView):

    permission_required = "import.pointage"

    def post(self, request):

        from django.utils import timezone

        user = request.user

        if not getattr(user, "is_superuser", False):

            return Response(
                {
                    "success": False,
                    "message": "Non autorisÃÂ©",
                },
                status=403,
            )

        batch_id = request.data.get("batch_id")

        reason = request.data.get("reason", "").strip()

        if not batch_id:

            return Response(
                {"success": False, "message": "batch_id requis"}, status=400
            )

        if not reason:

            return Response(
                {"success": False, "message": "Motif de rejet requis"}, status=400
            )

        # Resolve the single filiale database that owns this batch.

        db = find_filiale_db_for_batch(batch_id)

        if db is None:

            return Response(
                {
                    "success": False,
                    "message": "Aucun lot en attente trouvÃÂ© pour ce batch_id.",
                },
                status=404,
            )

        model_map = {
            "pointage": Pointage,
            "grand_materiel": Grand_Materiel,
            "affectation_materiel": Affectation_Materiel,
            "situation_materiel": Situation_Materiel,
            "site": Site,
            "famille_materiel": Famille_Materiel,
            "sous_famille_materiel": Sous_Famille_Materiel,
            "marque_materiel": Marque_Materiel,
            "type_marque": Type_Marque,
            "categorie_gm": Categorie_GM,
            "regularisation_gm": Regularisation_GM,
        }

        total_updated = 0

        importers_notified = {}

        from django.contrib.auth import get_user_model

        User = get_user_model()

        with transaction.atomic(using=db):

            for model_name, ModelClass in model_map.items():

                try:

                    qs = (
                        ModelClass.objects.using(db)
                        .select_for_update()
                        .filter(status="PENDING", import_batch_id=batch_id)
                    )

                    model_count = 0
                    model_import_dates = []

                    for obj in qs:

                        obj.status = "REJECTED"

                        obj.rejected_by = user

                        obj.rejected_at = timezone.now()

                        obj.rejection_reason = reason

                        obj.save(
                            using=db,
                            update_fields=[
                                "status",
                                "rejected_by",
                                "rejected_at",
                                "rejection_reason",
                            ],
                        )

                        total_updated += 1
                        model_count += 1

                        if obj.created_at:
                            model_import_dates.append(obj.created_at)

                        # Collect importer for notification
                        if obj.imported_by:
                            imp_id = obj.imported_by.id
                            if imp_id not in importers_notified:
                                importers_notified[imp_id] = {
                                    "models": [],
                                    "total_records": 0,
                                    "import_dates": [],
                                }
                            importers_notified[imp_id]["models"].append(model_name)
                            importers_notified[imp_id]["total_records"] += 1
                            if obj.created_at:
                                importers_notified[imp_id][
                                    "import_dates"
                                ].append(obj.created_at)

                    if model_count > 0:
                        pass  # model processed

                except Exception as e:

                    return Response(
                        {
                            "success": False,
                            "message": f"Erreur sur {model_name}: {str(e)}",
                        },
                        status=500,
                    )

        # Send notification to importers (central DB: Notification)

        if importers_notified:

            try:

                from .models.notification import Notification

                rejection_time = timezone.now()

                for importer_id, details in importers_notified.items():

                    importer = User.objects.get(id=importer_id)

                    models_str = ", ".join(set(details["models"]))
                    import_dt_min = (
                        min(details["import_dates"]) if details["import_dates"] else None
                    )
                    import_dt_max = (
                        max(details["import_dates"]) if details["import_dates"] else None
                    )
                    import_datetime = import_dt_min

                    import_datetime_str = ""
                    if import_dt_min and import_dt_max:
                        if import_dt_min == import_dt_max:
                            import_datetime_str = import_dt_min.strftime("%d/%m/%Y %H:%M")
                        else:
                            import_datetime_str = (
                                f"{import_dt_min.strftime('%d/%m/%Y %H:%M')} - "
                                f"{import_dt_max.strftime('%d/%m/%Y %H:%M')}"
                            )

                    title = f"Import rejeté: lot {batch_id[:8]}"
                    message_lines = [
                        f"Votre import (lot {batch_id}) a été rejeté par l'administrateur.",
                        f"Modèle(s) concerné(s): {models_str}",
                        f"Nombre d'enregistrements: {details['total_records']}",
                        f"Date(s) d'import: {import_datetime_str or 'N/A'}",
                        f"Date de rejet: {rejection_time.strftime('%d/%m/%Y %H:%M')}",
                        f"Motif: {reason}",
                    ]
                    message = "\n".join(message_lines)

                    # Update the importer's existing PENDING_IMPORT notification to IMPORT_REJECTED,
                    # or create a new one if none found (e.g., legacy data).
                    updated = Notification.objects.filter(
                        type="PENDING_IMPORT",
                        related_object_id=str(batch_id),
                        recipient=importer,
                    ).update(
                        type="IMPORT_REJECTED",
                        title=title,
                        message=message,
                        is_read=False,
                        related_object_type="batch",
                        import_model=models_str,
                        record_count=details["total_records"],
                        import_datetime=import_datetime,
                        rejection_datetime=rejection_time,
                        rejection_reason=reason,
                    )

                    if not updated:

                        Notification.objects.create(
                            recipient=importer,
                            title=title,
                            message=message,
                            type="IMPORT_REJECTED",
                            related_object_type="batch",
                            related_object_id=batch_id,
                            created_by=user,
                            import_model=models_str,
                            record_count=details["total_records"],
                            import_datetime=import_datetime,
                            rejection_datetime=rejection_time,
                            rejection_reason=reason,
                        )

            except Exception:

                pass

        return Response(
            {
                "success": True,
                "updated": total_updated,
                "notified_importers": len(importers_notified),
            }
        )


class NotificationViewSet(PagePermissionRequiredMixin, viewsets.ModelViewSet):

    serializer_class = NotificationSerializer

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):

        return Notification.objects.filter(recipient=self.request.user).order_by(
            "-created_at"
        )

    @action(detail=True, methods=["patch"])
    def read(self, request, pk=None):

        notification = self.get_object()

        notification.is_read = True

        notification.save()

        return Response({"success": True})

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):

        Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True
        )

        return Response({"success": True})

    def destroy(self, request, pk=None):
        notification = self.get_object()
        notification.delete()
        return Response({"success": True})































































from django.conf import settings
from api.permissions import ExternalServiceDashboardPermission, can_access_filiale
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


class MgtDashboardDecadaireView(APIView):
    permission_classes = [IsAuthenticated, ExternalServiceDashboardPermission("analyse.mgt_dashboard")]
    def get(self, request):
        user = request.user
        filiale = request.query_params.get('filiale')
        if getattr(user, 'is_external_service', False) and filiale and filiale != 'toutes':
            if filiale not in settings.FILIALE_DATABASES or not can_access_filiale(user, filiale):
                return Response({'error': 'Code filiale invalide ou non autorisé'}, status=400)
        data = MgtDashboardService.get_decadaire_data(
            user,
            request.query_params.get('famille'),
            request.query_params.get('site'),
            filiale,
            request.query_params.get('mmaa'),
            request.query_params.get('decade'),
            request.query_params.get('date_debut'),
            request.query_params.get('date_fin'),
            page=int(request.query_params.get('page') or 1),
            page_size=int(request.query_params.get('page_size') or 100),
        )
        return Response(data)

class MgtDashboardMensuelView(APIView):
    permission_classes = [IsAuthenticated, ExternalServiceDashboardPermission("analyse.mgt_dashboard")]
    def get(self, request):
        user = request.user
        filiale = request.query_params.get('filiale')
        if getattr(user, 'is_external_service', False) and filiale and filiale != 'toutes':
            if filiale not in settings.FILIALE_DATABASES or not can_access_filiale(user, filiale):
                return Response({'error': 'Code filiale invalide ou non autorisé'}, status=400)
        data = MgtDashboardService.get_mensuel_data(
            user,
            request.query_params.get('famille'),
            request.query_params.get('site'),
            filiale,
            request.query_params.get('mmaa'),
            request.query_params.get('date_debut'),
            request.query_params.get('date_fin'),
            page=int(request.query_params.get('page') or 1),
            page_size=int(request.query_params.get('page_size') or 100),
        )
        return Response(data)


class MgtDashboardDecadaireRecapView(APIView):
    permission_classes = [IsAuthenticated, ExternalServiceDashboardPermission("analyse.mgt_dashboard")]
    def get(self, request):
        user = request.user
        filiale = request.query_params.get('filiale')
        if getattr(user, 'is_external_service', False) and filiale and filiale != 'toutes':
            if filiale not in settings.FILIALE_DATABASES or not can_access_filiale(user, filiale):
                return Response({'error': 'Code filiale invalide ou non autorisé'}, status=400)
        data = MgtDashboardService.get_decadaire_recap_data(
            user,
            request.query_params.get('famille'),
            request.query_params.get('site'),
            filiale,
            request.query_params.get('mmaa'),
            request.query_params.get('decade'),
            request.query_params.get('date_debut'),
            request.query_params.get('date_fin'),
        )
        return Response(data)


class MgtDashboardMensuelRecapView(APIView):
    permission_classes = [IsAuthenticated, ExternalServiceDashboardPermission("analyse.mgt_dashboard")]
    def get(self, request):
        user = request.user
        filiale = request.query_params.get('filiale')
        if getattr(user, 'is_external_service', False) and filiale and filiale != 'toutes':
            if filiale not in settings.FILIALE_DATABASES or not can_access_filiale(user, filiale):
                return Response({'error': 'Code filiale invalide ou non autorisé'}, status=400)
        data = MgtDashboardService.get_mensuel_recap_data(
            user,
            request.query_params.get('famille'),
            request.query_params.get('site'),
            filiale,
            request.query_params.get('mmaa'),
            request.query_params.get('date_debut'),
            request.query_params.get('date_fin'),
        )
        return Response(data)

