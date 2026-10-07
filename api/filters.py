import re

from django.db.models import Q
from django.utils import timezone
from rest_framework import filters

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _date_filter_q(field: str, term: str) -> Q:
    """Build a Q filter for a DateField from a flexible user term.

    Accepts day, month, year in any order separated by / or - (e.g. "29",
    "07", "29/07", "29/07/2025", "2025-07-29"). Numbers > 31 are treated as
    years, numbers > 12 as days, and numbers <= 12 match either day or month.
    """
    q = Q()
    parts = [p for p in term.replace("-", "/").split("/") if p.isdigit()]
    for raw in parts:
        n = int(raw)
        if n > 31:
            q &= Q(**{f"{field}__year": n})
        elif n > 12:
            q &= Q(**{f"{field}__day": n})
        else:
            q &= (Q(**{f"{field}__day": n}) | Q(**{f"{field}__month": n}))
    return q


class GrandMaterielOrderingFilter(filters.OrderingFilter):
    ordering_field_map = {
        "libelle_famille": "code_sous_famille_materiel__code_famille_materiel__libelle_famille",
        "libelle_categorie": "code_sous_famille_materiel__code_famille_materiel__code_categorie_gm__libelle_categorie",
        "libelle_marque": "code_type_marque__code_marque__libelle_marque",
        "libelle_filiale": "code_filiale_g__libelle_filiale",
        "libelle_sous_famille": "code_sous_famille_materiel__libelle_sous_famille",
        "libelle_type_marque": "code_type_marque__libelle_type_marque",
        "code_filiale_g": "code_filiale_g__code_filiale",
        "code_sous_famille": "code_sous_famille_materiel__code_sous_famille",
        "code_type_marque": "code_type_marque__code_type_marque",
    }

    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)
        if not ordering:
            return ordering
        mapped = []
        for field in ordering:
            descending = field.startswith("-")
            clean_field = field.lstrip("-")
            mapped_field = self.ordering_field_map.get(clean_field, clean_field)
            mapped.append(f"-{mapped_field}" if descending else mapped_field)
        return mapped


def _bool_param(term: str):
    return term.strip().lower() in ("true", "1", "yes", "oui", "vrai")


class AffectationMaterielFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        code_affectation = request.query_params.get("code_affectation")
        code_materiel = request.query_params.get("code_materiel")
        code_site = request.query_params.get("code_site")
        code_filiale = request.query_params.get("code_filiale")
        date_debut = request.query_params.get("date_debut")
        date_fin = request.query_params.get("date_fin")
        est_bloque = request.query_params.get("est_bloque")
        date_affectation = request.query_params.get("date_affectation")
        nbr_jours_affectation = request.query_params.get("nbr_jours_affectation")

        if code_affectation:
            queryset = queryset.filter(code_affectation__icontains=code_affectation)
        if code_materiel:
            queryset = queryset.filter(code_materiel__code_materiel__icontains=code_materiel)
        if code_site:
            queryset = queryset.filter(code_site__code_site__icontains=code_site)
        if code_filiale:
            queryset = queryset.filter(code_filiale_mere__code_filiale__icontains=code_filiale)
        if date_debut:
            queryset = queryset.filter(date_affectation__gte=date_debut)
        if date_fin:
            queryset = queryset.filter(date_affectation__lte=date_fin)
        if date_affectation:
            queryset = queryset.filter(_date_filter_q("date_affectation", date_affectation))
        if nbr_jours_affectation:
            queryset = queryset.filter(nbr_jours_affectation__icontains=nbr_jours_affectation)
        if est_bloque is not None and est_bloque != "":
            queryset = queryset.filter(est_bloque=_bool_param(est_bloque))
        return queryset


class SituationMaterielFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        id_situation = request.query_params.get("id_situation")
        code_affectation = request.query_params.get("code_affectation")
        code_materiel = request.query_params.get("code_materiel")
        code_type_situation = request.query_params.get("code_type_situation")
        code_type_affectation = request.query_params.get("code_type_affectation")
        etat_materiel = request.query_params.get("etat_materiel")
        code_site = request.query_params.get("code_site")
        code_filiale = request.query_params.get("code_filiale")
        date_debut = request.query_params.get("date_debut")
        date_fin = request.query_params.get("date_fin")
        est_bloque = request.query_params.get("est_bloque")

        date_situation = request.query_params.get("date_situation")
        date_modification = request.query_params.get("date_modification")
        etat_materiel_libelle = request.query_params.get("etat_materiel_libelle")
        type_situation_libelle = request.query_params.get("type_situation_libelle")
        type_affectation_libelle = request.query_params.get("type_affectation_libelle")

        if id_situation:
            queryset = queryset.filter(id_situation__icontains=id_situation)
        if code_affectation:
            queryset = queryset.filter(affectation_id__code_affectation__icontains=code_affectation)
        if code_materiel:
            queryset = queryset.filter(affectation_id__code_materiel__code_materiel__icontains=code_materiel)
        if code_type_situation:
            queryset = queryset.filter(type_situation_id__code_type_situation__icontains=code_type_situation)
        if code_type_affectation:
            queryset = queryset.filter(type_situation_id__code_type_affectation__code_type_affectation__icontains=code_type_affectation)
        if etat_materiel:
            queryset = queryset.filter(code_type_etat_materiel__code_type_etat_materiel__icontains=etat_materiel)
        if code_site:
            queryset = queryset.filter(affectation_id__code_site__code_site__icontains=code_site)
        if code_filiale:
            queryset = queryset.filter(affectation_id__code_filiale_mere__code_filiale__icontains=code_filiale)
        if etat_materiel_libelle:
            queryset = queryset.filter(
                Q(code_type_etat_materiel__code_type_etat_materiel__icontains=etat_materiel_libelle)
                | Q(code_type_etat_materiel__libelle_type_etat_materiel__icontains=etat_materiel_libelle)
            )
        if type_situation_libelle:
            queryset = queryset.filter(
                Q(type_situation_id__code_type_situation__icontains=type_situation_libelle)
                | Q(type_situation_id__libelle_type_situation__icontains=type_situation_libelle)
            )
        if type_affectation_libelle:
            queryset = queryset.filter(
                Q(type_situation_id__code_type_affectation__code_type_affectation__icontains=type_affectation_libelle)
                | Q(
                    type_situation_id__code_type_affectation__libelle_type_affectation__icontains=type_affectation_libelle
                )
            )
        if date_situation:
            queryset = queryset.filter(_date_filter_q("date_situation", date_situation))
        if date_modification:
            queryset = queryset.filter(_date_filter_q("date_modification", date_modification))
        if date_debut:
            queryset = queryset.filter(date_situation__gte=date_debut)
        if date_fin:
            queryset = queryset.filter(date_situation__lte=date_fin)
        if est_bloque is not None and est_bloque != "":
            queryset = queryset.filter(est_bloque=_bool_param(est_bloque))
        return queryset


class GrandMaterielFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        code_materiel = request.query_params.get("code_materiel")
        materiel_id = request.query_params.get("id")
        user_id = request.query_params.get("user_id")
        designation = request.query_params.get("designation")
        num_serie = request.query_params.get("num_serie")
        immatriculation = request.query_params.get("immatriculation")
        code_sous_famille = request.query_params.get("code_sous_famille")
        code_type_marque = request.query_params.get("code_type_marque")
        libelle_sous_famille = request.query_params.get("libelle_sous_famille")
        libelle_type_marque = request.query_params.get("libelle_type_marque")
        code_filiale = request.query_params.get("code_filiale")
        libelle_filiale = request.query_params.get("libelle_filiale")
        libelle_famille = request.query_params.get("libelle_famille")
        libelle_categorie = request.query_params.get("libelle_categorie")
        libelle_marque = request.query_params.get("libelle_marque")
        est_bloque = request.query_params.get("est_bloque")
        date_acquisition = request.query_params.get("date_acquisition")
        date_modification = request.query_params.get("date_modification")
        created_at = request.query_params.get("created_at")
        updated_at = request.query_params.get("updated_at")
        valeur_acquisition = request.query_params.get("valeur_acquisition")
        valeur_remplacement = request.query_params.get("valeur_remplacement")
        taux_amortissement = request.query_params.get("taux_amortissement")
        puissance_materiel = request.query_params.get("puissance_materiel")
        filtered = request.query_params.get("filtered")

        if code_materiel:
            queryset = queryset.filter(code_materiel__icontains=code_materiel)
        if materiel_id:
            queryset = queryset.filter(id__icontains=materiel_id)
        if user_id:
            if user_id.isdigit():
                queryset = queryset.filter(user_id=int(user_id))
            else:
                queryset = queryset.filter(user_id__username__icontains=user_id)
        if designation:
            queryset = queryset.filter(designation__icontains=designation)
        if num_serie:
            queryset = queryset.filter(num_serie__icontains=num_serie)
        if immatriculation:
            queryset = queryset.filter(immatriculation__icontains=immatriculation)
        if code_sous_famille:
            queryset = queryset.filter(code_sous_famille_materiel__code_sous_famille__icontains=code_sous_famille)
        if code_type_marque:
            queryset = queryset.filter(code_type_marque__code_type_marque__icontains=code_type_marque)
        if libelle_sous_famille:
            queryset = queryset.filter(code_sous_famille_materiel__libelle_sous_famille__icontains=libelle_sous_famille)
        if libelle_type_marque:
            queryset = queryset.filter(code_type_marque__libelle_type_marque__icontains=libelle_type_marque)
        if code_filiale:
            queryset = queryset.filter(code_filiale_g__code_filiale__icontains=code_filiale)
        if libelle_filiale:
            queryset = queryset.filter(code_filiale_g__libelle_filiale__icontains=libelle_filiale)
        if libelle_famille:
            queryset = queryset.filter(
                code_sous_famille_materiel__code_famille_materiel__libelle_famille__icontains=libelle_famille
            )
        if libelle_categorie:
            queryset = queryset.filter(
                code_sous_famille_materiel__code_famille_materiel__code_categorie_gm__libelle_categorie__icontains=libelle_categorie
            )
        if libelle_marque:
            queryset = queryset.filter(
                code_type_marque__code_marque__libelle_marque__icontains=libelle_marque
            )
        if date_acquisition:
            queryset = queryset.filter(_date_filter_q("date_acquisition", date_acquisition))
        if date_modification:
            queryset = queryset.filter(_date_filter_q("date_modification", date_modification))
        if created_at:
            queryset = queryset.filter(_date_filter_q("created_at", created_at))
        if updated_at:
            queryset = queryset.filter(_date_filter_q("updated_at", updated_at))
        if valeur_acquisition:
            queryset = queryset.filter(valeur_acquisition__icontains=valeur_acquisition)
        if valeur_remplacement:
            queryset = queryset.filter(valeur_remplacement__icontains=valeur_remplacement)
        if taux_amortissement:
            queryset = queryset.filter(taux_amortissement__icontains=taux_amortissement)
        if puissance_materiel:
            queryset = queryset.filter(puissance_materiel__icontains=puissance_materiel)
        if est_bloque is not None and est_bloque != "":
            queryset = queryset.filter(est_bloque=_bool_param(est_bloque))

        # Filter by type_affectation when filtered=true
        # Excludes materiel with latest situation type_affectation in 06, 07, 08 or libelle "NON FOURNIE"
        if filtered and filtered.lower() == "true":
            from django.db.models import OuterRef, Subquery, Q
            from api.models import Situation_Materiel, Type_Situation, Type_Affectation

            latest_situation = Situation_Materiel.objects.filter(
                affectation_id__code_materiel__code_materiel=OuterRef("code_materiel"),
                date_situation__date__lte=timezone.now().date(),
            ).order_by("-date_situation__date", "-id")

            latest_type_affectation_code = Subquery(
                latest_situation.values("type_situation_id__code_type_affectation__code_type_affectation")[:1]
            )
            latest_type_affectation_libelle = Subquery(
                latest_situation.values("type_situation_id__code_type_affectation__libelle_type_affectation")[:1]
            )

            queryset = queryset.annotate(
                latest_type_affectation_code=latest_type_affectation_code,
                latest_type_affectation_libelle=latest_type_affectation_libelle,
            ).exclude(
                Q(latest_type_affectation_code__in=["06","07", "08"]) | Q(latest_type_affectation_libelle="NON FOURNIE")
            )

        return queryset


class PointageOrderingFilter(GrandMaterielOrderingFilter):
    """Map the API column keys exposed by PointageSerializer to ORM paths."""

    ordering_field_map = {
        "code_affectation": "affectation_id__code_affectation",
        "code_materiel": "affectation_id__code_materiel__code_materiel",
        "code_site": "affectation_id__code_site__code_site",
        "code_filiale": "affectation_id__code_filiale_mere__code_filiale",
        "user": "user_id__username",
    }


class PointageFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        code_affectation = request.query_params.get("code_affectation")
        code_materiel = request.query_params.get("code_materiel")
        mmaa = request.query_params.get("mmaa")
        mmaa_debut = request.query_params.get("mmaa_debut")
        mmaa_fin = request.query_params.get("mmaa_fin")
        code_site = request.query_params.get("code_site")
        code_filiale = request.query_params.get("code_filiale")
        est_bloque = request.query_params.get("est_bloque")
        taux_location = request.query_params.get("taux_location")
        heures_service = request.query_params.get("heures_service")
        heures_chomage = request.query_params.get("heures_chomage")
        heures_panne = request.query_params.get("heures_panne")
        potentiel = request.query_params.get("potentiel")
        montant_service = request.query_params.get("montant_service")
        montant_chomage = request.query_params.get("montant_chomage")
        montant_panne = request.query_params.get("montant_panne")
        date_modification = request.query_params.get("date_modification")
        created_at = request.query_params.get("created_at")
        updated_at = request.query_params.get("updated_at")
        user = request.query_params.get("user")

        if code_affectation:
            queryset = queryset.filter(affectation_id__code_affectation__icontains=code_affectation)
        if code_materiel:
            queryset = queryset.filter(affectation_id__code_materiel__code_materiel__icontains=code_materiel)
        if mmaa:
            # Keep exact matching for a full ISO date, otherwise allow the same
            # flexible day/month/year input as the other date filters.
            if _ISO_DATE_RE.match(mmaa.strip()):
                queryset = queryset.filter(mmaa=mmaa.strip())
            else:
                queryset = queryset.filter(_date_filter_q("mmaa", mmaa))
        if mmaa_debut:
            queryset = queryset.filter(mmaa__gte=mmaa_debut)
        if mmaa_fin:
            queryset = queryset.filter(mmaa__lte=mmaa_fin)
        if code_site:
            queryset = queryset.filter(affectation_id__code_site__code_site__icontains=code_site)
        if code_filiale:
            queryset = queryset.filter(affectation_id__code_filiale_mere__code_filiale__icontains=code_filiale)
        if user:
            queryset = queryset.filter(user_id__username__icontains=user)
        for term, field in (
            (taux_location, "taux_location"),
            (heures_service, "heures_service"),
            (heures_chomage, "heures_chomage"),
            (heures_panne, "heures_panne"),
            (potentiel, "potentiel"),
            (montant_service, "montant_service"),
            (montant_chomage, "montant_chomage"),
            (montant_panne, "montant_panne"),
        ):
            if term:
                queryset = queryset.filter(**{f"{field}__icontains": term})
        if date_modification:
            queryset = queryset.filter(_date_filter_q("date_modification", date_modification))
        if created_at:
            queryset = queryset.filter(_date_filter_q("created_at", created_at))
        if updated_at:
            queryset = queryset.filter(_date_filter_q("updated_at", updated_at))
        if est_bloque is not None and est_bloque != "":
            queryset = queryset.filter(est_bloque=_bool_param(est_bloque))
        return queryset