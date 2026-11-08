"""External API views for Analyse quantitative, Analyse exploitation and Journal materiel.

All endpoints are read-only (GET only) and reuse the existing internal
calculation services, filters and serializers. They enforce the external
service filiale scoping introduced with ExternalServiceClient.allowed_filiales.
"""

from datetime import datetime

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.authentication import ExternalServiceJWTAuthentication
from api.filters import (
    GrandMaterielOrderingFilter,
    GrandMaterielFilter,
)
from api.models import Grand_Materiel
from api.permissions import (
    ExternalServiceDashboardPermission,
    can_include_pending_data,
    get_allowed_filiale_codes,
)
from api.serializers import GrandMaterielSerializer
from api.services.analyse_exploitation import AnalyseExploitation, AnalyseExploitationResume
from api.services.analyse_qunatitaive import AnalyseQuantitative, AnalyseQuantitativeResume
from api.multidb import affiliate_routing, filiale_db_name

FILIALE_INVALID = {"error": "Code filiale invalide ou non autorisé"}


def _validate_date(value, field_name):
    """Validate a date query parameter.

    Returns a ``datetime.date`` instance on success or ``None`` when the
    parameter is absent/empty (dates are optional). Raises ``ValueError``
    with a French, human-readable message when the value is present but
    has an invalid format or describes an impossible calendar date.
    """
    if value is None or value == "":
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ValueError(
            f"Le paramètre '{field_name}' doit avoir le format YYYY-MM-DD "
            f"(ex: 2026-01-31). Valeur reçue: '{value}'."
        )


def _validate_date_range(date_debut, date_fin):
    """Ensure ``date_debut`` is not after ``date_fin`` when both are set."""
    if date_debut is not None and date_fin is not None and date_debut > date_fin:
        raise ValueError(
            "La date de début doit être antérieure ou égale à la date de fin."
        )


def _parse_date_params(request):
    """Read, validate and return ``(date_debut, date_fin)`` as ``date`` objects.

    Missing/empty parameters are allowed and returned as ``None``. Any
    malformed or impossible date raises ``ValueError`` so the caller can
    reply with a controlled HTTP 400 instead of letting the ORM surface a
    500.
    """
    raw_debut = request.query_params.get("date_debut")
    raw_fin = request.query_params.get("date_fin")
    date_debut = _validate_date(raw_debut, "date_debut")
    date_fin = _validate_date(raw_fin, "date_fin")
    _validate_date_range(date_debut, date_fin)
    return date_debut, date_fin


def _analyse_filiale_codes(request):
    """Return the list of filiale codes to query for the analyse endpoints.

    - An explicit, authorized filiale scopes the query to that filiale.
    - ``toutes`` or an absent filiale param returns every authorized
      filiale (the two are equivalent for these endpoints).
    - An invalid/unauthorized filiale returns ``None`` so the caller can
      reply with HTTP 400.
    """
    requested = (
        request.query_params.get("code_filiale")
        or request.query_params.get("filiale")
    )
    if not requested or requested == "toutes":
        codes = get_allowed_filiale_codes(request.user)
        return codes if codes else None
    filiale = _validate_filiale(request)
    if filiale is None:
        return None
    return [filiale]


def _is_external_service(user) -> bool:
    return bool(user) and bool(getattr(user, "is_external_service", False))


def _validate_filiale(request):
    """Return the requested filiale code or None.

    External services must request an explicit, authorized filiale. A
    missing or unauthorized code yields HTTP 400 with the standard error
    payload. ``toutes`` is rejected for external services (they must be
    scoped to a single filiale).
    """
    user = request.user
    requested = (
        request.query_params.get("code_filiale")
        or request.query_params.get("filiale")
    )
    if not requested:
        return None
    if requested == "toutes":
        if _is_external_service(user):
            return None
        return "toutes"
    if requested not in settings.FILIALE_DATABASES:
        return None
    if requested not in get_allowed_filiale_codes(user):
        return None
    return requested


def _include_pending(request) -> bool:
    """Pending data is never exposed to external services."""
    return bool(
        request.query_params.get("include_pending", "false").lower() == "true"
        and can_include_pending_data(request.user)
    )


class ExternalAnalyseQuantitativeView(APIView):
    """GET /api/external/analyse-quantitative/

    Detailed analyse quantitative rows per sous-famille. Reuses
    AnalyseQuantitative.get_situations. No pagination (same as internal
    /api/aqtp/).
    """

    authentication_classes = (ExternalServiceJWTAuthentication,)
    permission_classes = (IsAuthenticated, ExternalServiceDashboardPermission)
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        codes = _analyse_filiale_codes(request)
        if codes is None:
            return Response(FILIALE_INVALID, status=status.HTTP_400_BAD_REQUEST)
        try:
            date_debut, date_fin = _parse_date_params(request)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        include_pending = _include_pending(request)
        rows = []
        for code in codes:
            rows.extend(
                AnalyseQuantitative.get_situations(
                    code_filiale=code,
                    date_debut=date_debut,
                    date_fin=date_fin,
                    include_pending=include_pending,
                    using=filiale_db_name(code),
                )
            )
        return Response(rows)


class ExternalAnalyseQuantitativeRecapView(APIView):
    """GET /api/external/analyse-quantitative-recap/

    Aggregate analyse quantitative summary. Reuses
    AnalyseQuantitativeResume.get_situations_resume for a single filiale;
    for all filiales merges AnalyseQuantitative.get_situations rows and
    applies the weighted rollup (age_moyen = sum(age_total)/sum(nbr)).
    """

    authentication_classes = (ExternalServiceJWTAuthentication,)
    permission_classes = (IsAuthenticated, ExternalServiceDashboardPermission)
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        codes = _analyse_filiale_codes(request)
        if codes is None:
            return Response(FILIALE_INVALID, status=status.HTTP_400_BAD_REQUEST)
        try:
            date_debut, date_fin = _parse_date_params(request)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        include_pending = _include_pending(request)

        if len(codes) == 1:
            return Response(
                AnalyseQuantitativeResume.get_situations_resume(
                    code_filiale=codes[0],
                    date_debut=date_debut,
                    date_fin=date_fin,
                    include_pending=include_pending,
                    using=filiale_db_name(codes[0]),
                )
            )

        rows = []
        for code in codes:
            rows.extend(
                AnalyseQuantitative.get_situations(
                    code_filiale=code,
                    date_debut=date_debut,
                    date_fin=date_fin,
                    include_pending=include_pending,
                    using=filiale_db_name(code),
                )
            )
        return Response(self._merge(rows))

    @staticmethod
    def _merge(rows):
        nbr_total = 0
        devider = 0
        age_total = 0
        exp_service = 0
        exp_chomage = 0
        exp_panne = 0
        imm_chomage = 0
        imm_reparation = 0
        imm_autre = 0
        rep_ALREM = 0
        rep_autre = 0

        for r in rows:
            nbr_total += r.get("nbr") or 0
            age_total += r.get("age_total") or 0
            if r.get("age_total") > 0:
                devider += r.get("nbr") or 0
            exp_service += r["exploitation"]["en_service"]
            exp_chomage += r["exploitation"]["en_chomage"]
            exp_panne += r["exploitation"]["en_panne"]
            imm_chomage += r["immobilise"]["en_chomage"]
            imm_reparation += r["immobilise"]["en_reparation"]
            imm_autre += r["immobilise"]["autre"]
            rep_ALREM += r["reparation"]["ALREM"]
            rep_autre += r["reparation"]["autre"]

        age_moyen = (age_total / devider) if devider else 0

        return {
            "nombre_totale": nbr_total,
            "age_moyen": int(age_moyen),
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

class ExternalAnalyseExploitationView(APIView):
    """GET /api/external/analyse-exploitation/

    Detailed analyse exploitation rows per sous-famille. Reuses
    AnalyseExploitation.get_pointages. No pagination (same as internal
    /api/aetp/).
    """

    authentication_classes = (ExternalServiceJWTAuthentication,)
    permission_classes = (IsAuthenticated, ExternalServiceDashboardPermission)
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        codes = _analyse_filiale_codes(request)
        if codes is None:
            return Response(FILIALE_INVALID, status=status.HTTP_400_BAD_REQUEST)
        try:
            date_debut, date_fin = _parse_date_params(request)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        include_pending = _include_pending(request)
        rows = []
        for code in codes:
            rows.extend(
                AnalyseExploitation.get_pointages(
                    code_filiale=code,
                    date_debut=date_debut,
                    date_fin=date_fin,
                    include_pending=include_pending,
                    using=filiale_db_name(code),
                )
            )
        return Response(rows)


class ExternalAnalyseExploitationRecapView(APIView):
    """GET /api/external/analyse-exploitation-recap/

    Aggregate analyse exploitation summary. Reuses
    AnalyseExploitationResume.get_pointages_resume for a single filiale;
    for all filiales merges AnalyseExploitation.get_pointages rows and
    applies the verified weighted rollup (potentiel_moyen and
    taux_location_moyen weighted by nbr_pointage; percentages recomputed
    from combined totals).
    """

    authentication_classes = (ExternalServiceJWTAuthentication,)
    permission_classes = (IsAuthenticated, ExternalServiceDashboardPermission)
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        codes = _analyse_filiale_codes(request)
        if codes is None:
            return Response(FILIALE_INVALID, status=status.HTTP_400_BAD_REQUEST)
        try:
            date_debut, date_fin = _parse_date_params(request)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        include_pending = _include_pending(request)

        if len(codes) == 1:
            return Response(
                AnalyseExploitationResume.get_pointages_resume(
                    code_filiale=codes[0],
                    date_debut=date_debut,
                    date_fin=date_fin,
                    include_pending=include_pending,
                    using=filiale_db_name(codes[0]),
                )
            )

        return Response(self._merge(codes, date_debut, date_fin, include_pending))

    @staticmethod
    def _merge(codes, date_debut, date_fin, include_pending):
        # Same rollup as the internal TP_AE_resume_API_View: call
        # AnalyseExploitationResume.get_pointages_resume per filiale and sum
        # the already-aggregated fields. Merging the raw per-sous-famille rows
        # from AnalyseExploitation.get_pointages would double-count a materiel
        # pointed in two filiales and would not produce the resume fields.
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

        for code in codes:
            row = AnalyseExploitationResume.get_pointages_resume(
                code_filiale=None,
                date_debut=date_debut,
                date_fin=date_fin,
                include_pending=include_pending,
                using=filiale_db_name(code),
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

        pct_hs = (heures_service * 100 / total_heures) if total_heures else 0
        pct_hc = (heures_chomage * 100 / total_heures) if total_heures else 0
        pct_hp = (heures_panne * 100 / total_heures) if total_heures else 0
        pct_ms = (montant_service * 100 / total_montants) if total_montants else 0
        pct_mc = (montant_chomage * 100 / total_montants) if total_montants else 0
        pct_mp = (montant_panne * 100 / total_montants) if total_montants else 0

        return {
            "nombre_existant": nombre_existant,
            "nombre_pointage": nombre_pointage,
            "nombre_materiels_pointes": nombre_materiels_pointes,
            "heures_service": heures_service,
            "heures_chomage": heures_chomage,
            "heures_panne": heures_panne,
            "montant_service": montant_service,
            "montant_chomage": montant_chomage,
            "montant_panne": montant_panne,
            "potentiel_moyen": (total_potentiel / nombre_pointage) if nombre_pointage else 0,
            "total_potentiel": total_potentiel,
            "total_potentiel_enregistre": total_potentiel_enregistre,
            "total_potentiel_calcule": total_potentiel_calcule,
            "taux_location_moyen": (total_taux / nombre_pointage) if nombre_pointage else 0,
            "pct_heures_service": pct_hs,
            "pct_heures_chomage": pct_hc,
            "pct_heures_panne": pct_hp,
            "pct_montant_service": pct_ms,
            "pct_montant_chomage": pct_mc,
            "pct_montant_panne": pct_mp,
        }


class ExternalJournalMaterielView(APIView):
    """GET /api/external/journal-materiel/

    Read-only journal materiel. Reuses GrandMaterielFilter,
    GrandMaterielOrderingFilter and GrandMaterielSerializer. Supports the
    same filters, search, ordering and pagination as the internal
    grand-materiel endpoint.

    A single authorized filiale is routed to that affiliate database.
    All authorized filiales are merged with a PK-first global pagination
    strategy: filters and ordering are applied within each database, the
    global count is the sum of per-database counts, and only the current
    page is serialized.
    """

    authentication_classes = (ExternalServiceJWTAuthentication,)
    permission_classes = (IsAuthenticated, ExternalServiceDashboardPermission)
    http_method_names = ["get"]
    serializer_class = GrandMaterielSerializer
    ordering_fields = tuple(GrandMaterielOrderingFilter.ordering_field_map.keys())

    def get(self, request, *args, **kwargs):
        from rest_framework.pagination import PageNumberPagination

        try:
            page_size = self._validate_page_size(request)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        paginator = PageNumberPagination()
        paginator.page_size = page_size
        paginator.page_size_query_param = "page_size"
        # max_page_size is set to the validated page_size so DRF's
        # get_page_size() returns exactly what the client asked for (it
        # clamps to max_page_size silently otherwise, which made ``count``
        # disagree with the number of returned rows).
        paginator.max_page_size = page_size

        user = request.user
        allowed_codes = get_allowed_filiale_codes(user)
        if not allowed_codes:
            return Response(FILIALE_INVALID, status=status.HTTP_400_BAD_REQUEST)

        requested = (
            request.query_params.get("code_filiale")
            or request.query_params.get("filiale")
        )

        if requested and requested != "toutes":
            if _is_external_service(user):
                if requested not in allowed_codes:
                    return Response(FILIALE_INVALID, status=status.HTTP_400_BAD_REQUEST)
                codes = [requested]
            else:
                filiale = _validate_filiale(request)
                if filiale is None or filiale not in allowed_codes:
                    return Response(FILIALE_INVALID, status=status.HTTP_400_BAD_REQUEST)
                if filiale == "toutes":
                    codes = allowed_codes
                else:
                    codes = [filiale]
        elif requested == "toutes":
            codes = allowed_codes
        else:
            codes = allowed_codes

        ordering = GrandMaterielOrderingFilter().get_ordering(request, None, self)
        if ordering is None:
            ordering = ["code_materiel"]

        if len(codes) == 1:
            return self._single_filiale(request, codes[0], ordering, paginator)

        return self._multi_filiale(request, codes, ordering, paginator)


    @staticmethod
    def _validate_page_size(request):
        """Return the requested page size, capped at 1000.

        Raises ``ValueError`` when the client explicitly requests more than
        the 1000-row cap so the caller can reply with a controlled HTTP 400
        instead of silently clamping the value (which made ``count`` disagree
        with the number of returned rows).
        """
        raw = request.query_params.get("page_size")
        if raw is None or raw == "":
            return 100
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValueError(
                "Le paramètre 'page_size' doit être un entier positif "
                f"(valeur reçue: '{raw}')."
            )
        if value < 1:
            raise ValueError(
                "Le paramètre 'page_size' doit être supérieur ou égal à 1 "
                f"(valeur reçue: '{raw}')."
            )
        if value > 1000:
            raise ValueError(
                "Le paramètre 'page_size' ne peut pas dépasser 1000 "
                f"(valeur reçue: '{raw}')."
            )
        return value

    def _single_filiale(self, request, code, ordering, paginator):
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
            qs = GrandMaterielFilter().filter_queryset(request, qs, self)
            qs = qs.order_by(*ordering)
            page = paginator.paginate_queryset(qs, request, view=self)
            if page is not None:
                serializer = GrandMaterielSerializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)
            serializer = GrandMaterielSerializer(qs, many=True)
            return Response(serializer.data)

    def _multi_filiale(self, request, codes, ordering, paginator):
        # Per-DB: filter + order, then project (pk, ordering fields) so the
        # global merge-sort does not materialize full model instances.
        sort_keys = self._ordering_sort_keys(ordering)
        tiebreakers = ["code_filiale_g__code_filiale", "pk"]

        merged = []
        total = 0
        for code in codes:
            with affiliate_routing(code):
                qs = (
                    Grand_Materiel.objects.using(filiale_db_name(code))
                    .select_related(
                        "code_sous_famille_materiel",
                        "code_type_marque",
                        "code_filiale_g",
                    )
                )
                qs = GrandMaterielFilter().filter_queryset(request, qs, self)
                qs = qs.order_by(*ordering, *tiebreakers)
                total += qs.count()
                for row in qs.values("pk", *sort_keys):
                    row["_filiale"] = code
                    merged.append(row)

        merged.sort(key=self._sort_key(sort_keys))

        page = paginator.paginate_queryset(merged, request, view=self)
        if page is None:
            page = merged

        page_pks = []
        by_filiale = {}
        for row in page:
            by_filiale.setdefault(row["_filiale"], []).append(row["pk"])
            page_pks.append(row["pk"])

        instances = []
        for code, pks in by_filiale.items():
            with affiliate_routing(code):
                instances.extend(
                    list(
                        Grand_Materiel.objects.using(filiale_db_name(code))
                        .filter(pk__in=pks)
                        .select_related(
                            "code_sous_famille_materiel",
                            "code_type_marque",
                            "user_id",
                            "code_filiale_g",
                        )
                    )
                )

        order_index = {pk: i for i, pk in enumerate(page_pks)}
        instances.sort(key=lambda o: order_index[o.pk])

        serializer = GrandMaterielSerializer(instances, many=True)
        return paginator.get_paginated_response(serializer.data)

    @staticmethod
    def _ordering_sort_keys(ordering):
        """Map API ordering keys to ORM field paths used in .values()."""
        mapping = GrandMaterielOrderingFilter.ordering_field_map
        keys = []
        for field in ordering:
            descending = field.startswith("-")
            clean = field.lstrip("-")
            mapped = mapping.get(clean, clean)
            keys.append(f"-{mapped}" if descending else mapped)
        return keys

    @staticmethod
    def _sort_key(sort_keys):
        def key(row):
            return tuple(row.get(k) for k in sort_keys)
        return key



