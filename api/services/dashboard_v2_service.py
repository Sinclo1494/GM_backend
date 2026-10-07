"""
Dashboard v2 — data foundation for the new dashboard.

This module is strictly additive and self-contained: it never imports,
subclasses or mutates `DashboardService` from `api.services.dashboard_service`
(the v1 `alerts` / `recentActivity` helpers it used to borrow were computed on
every call and never rendered, so they were dropped instead of being duplicated
here).

Conventions used by the whole service
-------------------------------------

*Material-scoped populations*: the parc is `Grand_Materiel` and every "how many
engins" figure is scoped to the **material**, never to the affectation — a
material with two affectations counts once (`_latest_situations` partitions the
window on `affectation_id__code_materiel`).

*Single filiale axis*: "which subsidiary owns this material" is always
`code_materiel__code_filiale_g` (the group the material belongs to, which is
what `_parc` counts). `Affectation_Materiel.code_filiale_mere` is the *booking*
subsidiary and is deliberately not used as a filter axis anymore.

*Money*: one CA definition, used by every endpoint —
``ca_realise = Σ(montant_service ?? heures_service × taux_location)``,
``ca_potentiel = Σ(potentiel × taux_location)``,
``total_facture = ca_realise + Σmontant_chomage + Σmontant_panne``,
``marge = ca_realise − Σmontant_regularisation``,
``manque_a_gagner = ca_potentiel − ca_realise`` (signed),
``ecart_cible = (ca_potentiel − ca_realise) / ca_potentiel × 100`` (positive is
good: the fleet billed less than its potential).

Two private helpers collapse the duplication that the v1 service suffers from:

* `_pointage_base(code_filiale, date_debut, date_fin, code_famille)` builds the
  canonical `Pointage` queryset (the filter chain was previously copy-pasted in
  ten different methods).
* `_niveau_grouping(niveau)` maps a niveau (`engin` / `famille` / `chantier` /
  `groupe`) to its `(value_field, label_field)` pair, so the 4-way
  if/elif/else collapse into a single parameterized call.

Evolution series group by *the same entity as the breakdown* and are then folded
back per period, so every monthly curve honours `niveau` (v1 ignored it).
"""

from collections import defaultdict
from datetime import date, datetime

from django.core.cache import cache
from django.db.models import (
    Case,
    Count,
    DecimalField,
    Exists,
    ExpressionWrapper,
    F,
    IntegerField,
    OuterRef,
    Q,
    Sum,
    Value,
    When,
    Window,
)
from django.db.models.functions import (
    Coalesce,
    RowNumber,
    TruncMonth,
    TruncQuarter,
)

from api.models import (
    Affectation_Materiel,
    Famille_Materiel,
    Filiale,
    Grand_Materiel,
    Pointage,
    Regularisation_GM,
    Situation_Materiel,
)

NIVEAU_DEFAUT = "engin"
NIVEAUX = ("engin", "famille", "chantier", "groupe")

RENTABILITE_CACHE_TTL = 300  # 5 minutes

#: (value_field, label_field) per niveau and per queryset "source".
#:   * ``pointage``    -> paths from ``Pointage`` through ``affectation_id``
#:   * ``parc``        -> paths on ``Grand_Materiel``
#:   * ``affectation`` -> paths on ``Affectation_Materiel``
_NIVEAU_GROUPING = {
    "engin": {
        "pointage": (
            "affectation_id__code_materiel",
            "affectation_id__code_materiel__designation",
        ),
        "parc": ("code_materiel", "designation"),
        "affectation": ("code_materiel", "designation"),
    },
    "famille": {
        "pointage": (
            "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille",
            "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille",
        ),
        "parc": (
            "code_sous_famille_materiel__code_famille_materiel__code_famille",
            "code_sous_famille_materiel__code_famille_materiel__libelle_famille",
        ),
        "affectation": (
            "code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille",
            "code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille",
        ),
    },
    "chantier": {
        "pointage": (
            "affectation_id__code_site",
            "affectation_id__code_site__libelle_site",
        ),
        "affectation": ("code_site", "code_site__libelle_site"),
    },
    "groupe": {
        "pointage": (
            "affectation_id__code_materiel__code_filiale_g",
            "affectation_id__code_materiel__code_filiale_g__libelle_filiale",
        ),
        "parc": ("code_filiale_g", "code_filiale_g__libelle_filiale"),
        "affectation": ("code_filiale_mere", "code_filiale_mere__libelle_filiale"),
    },
}

#: Fields summed on every ``Pointage`` series.
POINTAGE_SUM_FIELDS = ("heures_service", "heures_chomage", "heures_panne", "potentiel")

#: ``(type_affectation, type_situation)`` -> situation bucket.
#:
#: ``type_affectation`` is the *material's* administrative state (01 "En
#: exploitation", 02 "En réparation", 04 "Immobilisé", ...) and
#: ``type_situation`` its operating state (01 "En service", 02 "En chômage",
#: 03 "En panne", 04 "En réparation", ...). The parc KPI cards classify on the
#: PAIR, which is why a material sitting on an "Immobilisé" affectation with an
#: "En chômage" situation counts as *immobilisé*, not *en chômage*.
_SITUATION_CODES = {
    ("01", "01"): "en_service",
    ("01", "02"): "en_chomage",
    ("01", "03"): "en_panne",
    ("02", "06"): "alrem",
}

_SITUATION_KEYS = (
    "en_service",
    "en_chomage",
    "en_panne",
    "immobilise_base",
    "alrem",
    "en_reparation",
    # Pairs outside the reference grid (cessions, ré.formes, acquisition,
    # "NON FOURNIE" affectations). Kept as an explicit bucket so the donut
    # still reconciles with `parc_total` instead of silently dropping rows.
    "autres",
)

#: bucket -> donut label and -> donut code (the frontend colours by code).
_SITUATION_LABELS = {
    "en_service": "En service",
    "en_chomage": "En chômage",
    "en_panne": "En panne",
    "immobilise_base": "Immobilisé base",
    "alrem": "ALREM",
    "en_reparation": "En réparation",
    "autres": "Autres",
}

_SITUATION_DONUT_CODES = {
    "en_service": "01",
    "en_chomage": "02",
    "en_panne": "03",
    "alrem": "06",
    "en_reparation": "04",
    "immobilise_base": "07",
    "autres": "99",
}

#: Display order of the donut slices (largest operational buckets first).
_SITUATION_DONUT_ORDER = (
    "en_service",
    "en_chomage",
    "en_panne",
    "immobilise_base",
    "en_reparation",
    "alrem",
    "autres",
)


def _sum(field, max_digits=18, decimal_places=1):
    return Coalesce(
        Sum(field),
        Value(0, output_field=DecimalField(max_digits=max_digits, decimal_places=decimal_places)),
    )


def _sum_montant(field):
    return Coalesce(
        Sum(field),
        Value(0, output_field=DecimalField(max_digits=20, decimal_places=7)),
    )


def _count(filter_q=None):
    return Coalesce(
        Count("id", filter=filter_q),
        Value(0, output_field=IntegerField()),
    )


def _to_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _iso(value):
    return value.strftime("%Y-%m-%d") if value else None


class DashboardV2Service:
    """Aggregations backing the dashboard v2 endpoints.

    Every public method is a ``staticmethod`` returning plain dicts/lists, with
    the same ``float()`` / ``round()`` coercion pattern as ``DashboardService``.
    """

    # ------------------------------------------------------------------
    # Shared plumbing
    # ------------------------------------------------------------------
    @staticmethod
    def get_default_date_range():
        """Current month to date (mirrors ``AnalyseQuantitative.getCurrentMonthRange``)."""
        today = date.today()
        return today.replace(day=1), today

    @staticmethod
    def _resolve_range(date_debut=None, date_fin=None):
        debut = _to_date(date_debut)
        fin = _to_date(date_fin)
        if not debut or not fin:
            default_debut, default_fin = DashboardV2Service.get_default_date_range()
            debut = debut or default_debut
            fin = fin or default_fin
        return debut, fin

    @staticmethod
    def _niveau_grouping(niveau, source="pointage"):
        """Return ``(value_field, label_field)`` for ``niveau`` on ``source``."""
        niveau = (niveau or NIVEAU_DEFAUT).strip().lower()
        by_source = _NIVEAU_GROUPING.get(niveau) or _NIVEAU_GROUPING[NIVEAU_DEFAUT]
        return by_source.get(source) or by_source["pointage"]

    @staticmethod
    def _pointage_base(code_filiale=None, date_debut=None, date_fin=None, code_famille=None):
        """Canonical, un-branched ``Pointage`` queryset for the v2 dashboard."""
        qs = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )
        if code_filiale:
            qs = qs.filter(affectation_id__code_materiel__code_filiale_g=code_filiale)
        if code_famille:
            qs = qs.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )
        return qs

    @staticmethod
    def _pointage_aggregates():
        return {field: _sum(field) for field in POINTAGE_SUM_FIELDS}

    @staticmethod
    def _grouped(qs, niveau, aggregates, source="pointage", period_expr=TruncMonth):
        """Group ``qs`` by (period, entity) and return ``(rows, value_field, label_field)``.

        The period annotation is always exposed as ``mmaa_month`` so every caller
        folds the same key.
        """
        value_field, label_field = DashboardV2Service._niveau_grouping(niveau, source)
        fields = [value_field, label_field]
        if period_expr is not None:
            qs = qs.annotate(mmaa_month=period_expr("mmaa"))
            fields = ["mmaa_month"] + fields
        return list(qs.values(*fields).annotate(**aggregates)), value_field, label_field

    @staticmethod
    def _grouped_by_period(qs, aggregates, period=TruncMonth, period_field="mmaa"):
        """Group ``qs`` by period only (no niveau) — used by the global series."""
        return list(
            qs.annotate(mmaa_month=period(period_field))
            .values("mmaa_month")
            .annotate(**aggregates)
            .order_by("mmaa_month")
        )

    @staticmethod
    def _ratios(potentiel, heures_service, heures_chomage, heures_panne):
        """Hour-based ratios shared by every pointage series.

        All four maintenance indicators are distinct metrics (they used to be
        three copies of the same number):

        * ``disponibilite`` = (potentiel − heures_panne) / potentiel × 100
        * ``tmad`` (Taux Moyen de Disponibilité) = the availability actually
          *delivered* once the unemployment is removed:
          (potentiel − heures_panne − heures_chomage) / potentiel × 100
        * ``tam`` (Taux d'Aptitude à la Maintenance) = heures_service /
          (potentiel − heures_panne) × 100 — how much of the time the fleet was
          *not* down was actually worked
        * ``tip`` (Taux d'Indisponibilité pour Panne) = heures_panne /
          potentiel × 100 — the hours-based counterpart of ``taux_panne``

        A non-positive potential (or a non-positive maintenance base for TAM)
        yields 0.0 instead of raising/overflowing; ``tmad`` is left signed
        because a material can be idle (chômage) more than its potential.
        """
        if potentiel > 0:
            base_maintenance = potentiel - heures_panne
            disponibilite = base_maintenance / potentiel * 100
            tmad = (base_maintenance - heures_chomage) / potentiel * 100
            tam = (
                heures_service / base_maintenance * 100
                if base_maintenance > 0
                else 0.0
            )
            tip = heures_panne / potentiel * 100
            taux_utilisation = heures_service / potentiel * 100
            taux_chomage = heures_chomage / potentiel * 100
            rendement = disponibilite * taux_utilisation / 100
        else:
            disponibilite = tmad = tam = tip = 0.0
            taux_utilisation = taux_chomage = rendement = 0.0
        return {
            "disponibilite": round(disponibilite, 1),
            "tmad": round(tmad, 1),
            "tam": round(tam, 1),
            "tip": round(tip, 1),
            "taux_utilisation": round(taux_utilisation, 1),
            "taux_chomage": round(taux_chomage, 1),
            "rendement": round(rendement, 1),
        }

    @staticmethod
    def _raw_pointage(row, key=None, label=None):
        potentiel = float(row["potentiel"] or 0)
        heures_service = float(row["heures_service"] or 0)
        heures_chomage = float(row["heures_chomage"] or 0)
        heures_panne = float(row["heures_panne"] or 0)
        payload = {
            "potentiel": potentiel,
            "heures_service": heures_service,
            "heures_chomage": heures_chomage,
            "heures_panne": heures_panne,
        }
        payload.update(
            DashboardV2Service._ratios(potentiel, heures_service, heures_chomage, heures_panne)
        )
        if key is not None:
            payload["code"] = key
            payload["libelle"] = label or key
        return payload

    @staticmethod
    def _fold_periods(rows, period_field):
        """Collapse (period, entity) rows into one row per period.

        The accumulator MUST be bound inside the comprehension (``for period,
        bucket in ...``). Binding only ``period`` and referencing the loop
        variable ``bucket`` leaked from the accumulation loop above, so every
        emitted month repeated the *last* bucket's totals: the Disponibilité /
        Rendement evolution curves were flat lines carrying a single month's
        values under 8 different dates.
        """
        buckets = {}
        for row in rows:
            period = row[period_field]
            bucket = buckets.setdefault(
                period, {field: 0.0 for field in POINTAGE_SUM_FIELDS}
            )
            for field in POINTAGE_SUM_FIELDS:
                bucket[field] += float(row[field] or 0)

        return [
            {"mmaa": _iso(period), **DashboardV2Service._raw_pointage(bucket)}
            for period, bucket in sorted(
                buckets.items(), key=lambda kv: (kv[0] is None, kv[0])
            )
        ]

    @staticmethod
    def _fold_entities(rows, value_field, label_field):
        """Collapse rows into one row per entity code, ordered by code."""
        buckets = {}
        for row in rows:
            code = row[value_field]
            bucket = buckets.setdefault(
                code,
                {
                    "libelle": row[label_field],
                    **{field: 0.0 for field in POINTAGE_SUM_FIELDS},
                },
            )
            if bucket["libelle"] is None:
                bucket["libelle"] = row[label_field]
            for field in POINTAGE_SUM_FIELDS:
                bucket[field] += float(row[field] or 0)

        return [
            DashboardV2Service._raw_pointage(bucket, code, bucket["libelle"])
            for code, bucket in sorted(buckets.items(), key=lambda kv: (kv[0] is None, kv[0]))
        ]

    @staticmethod
    def _ratio_series(qs, niveau):
        """(evolution, breakdown) for the potentiel/heures ratio family.

        The evolution is grouped by the same entity as the breakdown, then
        folded back per month, so it honours ``niveau`` (v1 ignored it).
        """
        rows, value_field, label_field = DashboardV2Service._grouped(
            qs, niveau, DashboardV2Service._pointage_aggregates()
        )
        evolution = DashboardV2Service._fold_periods(rows, "mmaa_month")
        breakdown = DashboardV2Service._fold_entities(rows, value_field, label_field)
        return evolution, breakdown

    @staticmethod
    def _project(rows, *fields, keys=("code", "libelle")):
        """Keep only the given fields (plus the optional identity keys)."""
        projected = []
        for row in rows:
            item = {key: row.get(key) for key in keys if key in row}
            item.update({field: row[field] for field in fields})
            projected.append(item)
        return projected

    # ------------------------------------------------------------------
    # Situations / parc
    # ------------------------------------------------------------------
    @staticmethod
    def _latest_situations(code_filiale=None, date_fin=None, code_famille=None, include_inactive=False):
        """Latest situation of every *material* (not every affectation) at ``date_fin``.

        The window is partitioned by ``affectation_id__code_materiel`` so a
        material affected twice still yields a single row: the situation
        population and ``parc_total`` are then directly comparable, and the
        Aperçu donut total can never exceed the parc.

        By default, excludes materials whose latest situation has type_affectation
        in 06, 07, 08 or libelle 'NON FOURNIE'. Pass ``include_inactive=True``
        to bypass this filter (used for raw situation counts).
        """
        situations = Situation_Materiel.objects.filter(
            date_situation__date__lte=date_fin,
            est_bloque=False,
        )
        if code_filiale:
            situations = situations.filter(
                affectation_id__code_filiale_mere=code_filiale
            )
        if code_famille:
            situations = situations.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )
        qs = (
            situations.annotate(
                rn=Window(
                    expression=RowNumber(),
                    partition_by=[F("affectation_id__code_materiel")],
                    order_by=[F("date_situation").desc(), F("id").desc()],
                )
            )
            .filter(rn=1)
        )
        if not include_inactive:
            qs = qs.exclude(
                Q(type_situation_id__code_type_affectation__code_type_affectation__in=["06", "07", "08"]) |
                Q(type_situation_id__code_type_affectation__libelle_type_affectation="NON FOURNIE")
            )
        return qs

    @staticmethod
    def _situation_total(code_filiale=None, date_fin=None, code_famille=None):
        """Number of distinct materials carrying a latest situation.

        Published as ``globalKpis.situation_total`` so the UI can state how many
        of the ``parc_total`` materials are actually covered by a situation
        (materials without any situation row are simply absent).

        Excludes materials whose latest situation has type_affectation
        in 06, 07, 08 or libelle 'NON FOURNIE'.
        """
        return (
            DashboardV2Service._latest_situations(
                code_filiale, date_fin, code_famille, include_inactive=False
            ).aggregate(total=Count("affectation_id__code_materiel", distinct=True))[
                "total"
            ]
            or 0
        )

    @staticmethod
    def _situation_bucket(type_affectation, type_situation):
        """Classify one ``(type_affectation, type_situation)`` pair.

        Single source of truth shared by the KPI cards
        (``_situation_counts``) and the parc donut
        (``_situation_distribution``): both used to classify differently, so
        the donut reported 606 "En chômage" while the card reported 476 and the
        card buckets did not even add up to the parc.
        """
        key = _SITUATION_CODES.get((type_affectation, type_situation))
        if key:
            return key
        if type_affectation == "04":
            # Immobilisé affectation: "En réparation" is its own bucket, any
            # other situation is an immobilised base.
            if type_situation == "04":
                return "en_reparation"
            return "immobilise_base"
        return "autres"

    @staticmethod
    def _situation_counts(code_filiale=None, date_fin=None, code_famille=None):
        """Count the latest situation of every material by bucket.

        ``en_reparation`` is returned here as well (the overview surfaces it
        through ``maintenanceKpis.en_reparation``) so the sum of the buckets
        equals the situation population the donut renders.

        Excludes materials whose latest situation has type_affectation
        in 06, 07, 08 or libelle 'NON FOURNIE'.
        """
        counts = {key: 0 for key in _SITUATION_KEYS}
        latest = DashboardV2Service._latest_situations(code_filiale, date_fin, code_famille)

        for row in latest.values(
            "type_situation_id__code_type_affectation__code_type_affectation",
            "type_situation_id__code_type_situation",
        ):
            type_affectation = row["type_situation_id__code_type_affectation__code_type_affectation"]
            type_situation = row["type_situation_id__code_type_situation"]
            counts[DashboardV2Service._situation_bucket(type_affectation, type_situation)] += 1
        return counts

    @staticmethod
    def _parc(code_filiale=None, code_famille=None, est_bloque=False, date_fin=None):
        qs = Grand_Materiel.objects.all()
        if not est_bloque:
            qs = qs.filter(est_bloque=False)
        if code_filiale:
            # Filter by affectation's code_filiale_mere via latest situation
            from django.db.models import OuterRef, Subquery
            from api.models import Situation_Materiel

            latest_situation = Situation_Materiel.objects.filter(
                affectation_id__code_materiel__code_materiel=OuterRef("code_materiel"),
                date_situation__date__lte=date_fin,
            ).order_by("-date_situation__date", "-id")

            latest_filiale = Subquery(
                latest_situation.values("affectation_id__code_filiale_mere")[:1]
            )
            qs = qs.annotate(latest_filiale=latest_filiale).filter(latest_filiale=code_filiale)
        if code_famille:
            qs = qs.filter(
                code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )
        # Filter by type_affectation: exclude 06, 07, 08 and NON FOURNIE
        if date_fin:
            qs = DashboardV2Service._filter_parc_by_type_affectation(qs, date_fin)
        return qs

    @staticmethod
    def _parc_by_filiale(code_famille=None, date_fin=None):
        """Count materiel per filiale (via affectation filiale) when no filiale filter."""
        from django.db.models import OuterRef, Subquery, Count, F
        from api.models import Situation_Materiel

        qs = Grand_Materiel.objects.filter(est_bloque=False)
        if code_famille:
            qs = qs.filter(
                code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        # Annotate with latest situation's affectation filiale
        latest_situation = Situation_Materiel.objects.filter(
            affectation_id__code_materiel__code_materiel=OuterRef("code_materiel"),
            date_situation__date__lte=date_fin,
            est_bloque=False,
        ).order_by("-date_situation__date", "-id")

        # Filter by type_affectation: exclude 06, 07, 08 and NON FOURNIE
        if date_fin:
            qs = DashboardV2Service._filter_parc_by_type_affectation(qs, date_fin)

        # Group by filiale
        latest_filiale_subq = Subquery(
            latest_situation.values("affectation_id__code_filiale_mere")[:1]
        )
        latest_filiale_libelle_subq = Subquery(
            latest_situation.values("affectation_id__code_filiale_mere__libelle_filiale")[:1]
        )

        return list(
            qs.annotate(
                latest_filiale=latest_filiale_subq,
                latest_filiale_libelle=latest_filiale_libelle_subq,
            )
            .exclude(latest_filiale__isnull=True)
            .values(code_filiale=F("latest_filiale"), libelle_filiale=F("latest_filiale_libelle"))
            .annotate(totalMateriel=Count("code_materiel", distinct=True))
            .order_by("-totalMateriel")
        )

    @staticmethod
    def _filter_parc_by_type_affectation(qs, date_fin):
        """Filter Grand_Materiel queryset to exclude materiel with latest situation
        having type_affectation in 06, 07, 08 or libelle 'NON FOURNIE'."""
        from django.db.models import OuterRef, Subquery, Q
        from api.models import Situation_Materiel

        latest_situation = Situation_Materiel.objects.filter(
            affectation_id__code_materiel__code_materiel=OuterRef("code_materiel"),
            date_situation__date__lte=date_fin,
        ).order_by("-date_situation__date", "-id")

        latest_type_affectation_code = Subquery(
            latest_situation.values("type_situation_id__code_type_affectation__code_type_affectation")[:1]
        )
        latest_type_affectation_libelle = Subquery(
            latest_situation.values("type_situation_id__code_type_affectation__libelle_type_affectation")[:1]
        )

        return qs.annotate(
            latest_type_affectation_code=latest_type_affectation_code,
            latest_type_affectation_libelle=latest_type_affectation_libelle,
        ).exclude(
            Q(latest_type_affectation_code__in=["06","07", "08"]) | Q(latest_type_affectation_libelle="NON FOURNIE")
        )

    @staticmethod
    def _situation_distribution(code_filiale=None, date_fin=None, code_famille=None):
        """Latest situation of every material, one slice per situation bucket.

        The slices come from ``_situation_bucket``, the SAME classifier the KPI
        cards use, so a number shown on a card always equals the matching donut
        slice. Buckets are keyed by the ``(type_affectation, type_situation)``
        pair rather than by situation code alone: a material on an "Immobilisé"
        affectation carrying an "En chômage" situation is immobilised, not
        unemployed, and the old code-only grouping reported it as chômage (606
        on the donut vs 476 on the card).

        Two earlier defects are also fixed here:

        * The window filter of ``_latest_situations`` was applied in the SAME
          query as the ``Count``, so Django pulled the window's partition/order
          columns into ``GROUP BY``. Every group collapsed to ``count = 1`` and
          the donut rendered one slice per material, all labelled identically.
          The latest-per-material selection is now done in a sub-``id__in``
          query so the aggregation returns a handful of groups.
        * ``Type_Situation`` is unique per (code, type_affectation), so one
          situation code carries several labels ("En r\\"paration" and "En
          réparation" both under code ``04``). Grouping by bucket sidesteps that
          entirely: the slice label comes from the bucket, not from the row.
        """
        counts = DashboardV2Service._situation_counts(code_filiale, date_fin, code_famille)
        return [
            {
                "code_type_situation": _SITUATION_DONUT_CODES[bucket],
                "libelle_type_situation": _SITUATION_LABELS[bucket],
                "count": counts[bucket],
            }
            for bucket in _SITUATION_DONUT_ORDER
            if counts.get(bucket)
        ]

    @staticmethod
    def _regularisation(code_filiale=None, date_debut=None, date_fin=None, code_famille=None):
        """Regularisation amounts, optionally narrowed to a famille.

        ``Regularisation_GM`` hangs off ``Site`` only — there is no
        ``Site.code_materiel`` relation, so a famille cannot be reached by
        traversing the FK chain. A site is kept when it hosts at least one
        materiel of the famille (via ``Affectation_Materiel``), which matches
        the v1 service, where regularisation is only narrowed by ``code_filiale``.
        """
        qs = Regularisation_GM.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )
        if code_filiale:
            qs = qs.filter(code_site__code_filiale=code_filiale)
        if code_famille:
            qs = qs.filter(
                code_site__affectations__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            ).distinct()
        return qs

    @staticmethod
    def _ca_expr():
        """CA de location interne: stored amount, else heures x taux."""
        return ExpressionWrapper(
            Case(
                When(montant_service__isnull=False, then=F("montant_service")),
                When(
                    montant_service__isnull=True,
                    taux_location__isnull=False,
                    then=F("heures_service") * F("taux_location"),
                ),
                default=Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
                output_field=DecimalField(max_digits=30, decimal_places=7),
            ),
            output_field=DecimalField(max_digits=30, decimal_places=7),
        )

    @staticmethod
    def _cout_panne_expr():
        return ExpressionWrapper(
            Case(
                When(
                    taux_location__isnull=False,
                    then=F("heures_panne") * F("taux_location"),
                ),
                default=Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
                output_field=DecimalField(max_digits=30, decimal_places=7),
            ),
            output_field=DecimalField(max_digits=30, decimal_places=7),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @staticmethod
    def get_overview(code_filiale=None, date_debut=None, date_fin=None, code_famille=None):
        date_debut, date_fin = DashboardV2Service._resolve_range(date_debut, date_fin)

        counts = DashboardV2Service._situation_counts(code_filiale, date_fin, code_famille)
        pointages = DashboardV2Service._pointage_base(
            code_filiale, date_debut, date_fin, code_famille
        )
        pointage_agg = pointages.aggregate(**DashboardV2Service._pointage_aggregates())
        reg_total = DashboardV2Service._regularisation(
            code_filiale, date_debut, date_fin, code_famille
        ).aggregate(total=_sum_montant("montant_regularisation"))["total"]

        parc = DashboardV2Service._parc(code_filiale, code_famille, date_fin=date_fin)
        # True elapsed years (not a year-number difference) measured against
        # `date_fin`, and materials acquired *after* the period are excluded
        # (they would otherwise drag the average down with a negative age).
        # Computed in Python from a single narrow column: the "subtract 1 when
        # the anniversary has not happened yet" rule needs an expression-level
        # comparison, which Django's `ExtractMonth(...) > Value(...)` does not
        # support (comparison operators are not defined on expressions).
        acquisitions = list(
            parc.filter(date_acquisition__isnull=False, date_acquisition__lte=date_fin)
            .values_list("date_acquisition", flat=True)
        )
        ages = [
            (date_fin.year - acquired.year) - (1 if acquired.month > date_fin.month else 0)
            for acquired in acquisitions
        ]
        age_moyen = int(sum(ages) / len(ages)) if ages else 0

        potentiel_total = float(pointage_agg["potentiel"] or 0)
        heures_service = float(pointage_agg["heures_service"] or 0)
        heures_chomage = float(pointage_agg["heures_chomage"] or 0)
        heures_panne = float(pointage_agg["heures_panne"] or 0)
        ratios = DashboardV2Service._ratios(
            potentiel_total, heures_service, heures_chomage, heures_panne
        )

        parc_total = parc.count()

        # Filiale distribution (only when no filiale filter is applied)
        filiale_distribution = []
        if not code_filiale:
            filiale_distribution = DashboardV2Service._parc_by_filiale(code_famille, date_fin)

        global_kpis = {
            "parc_total": parc_total,
            "situation_total": DashboardV2Service._situation_total(
                code_filiale, date_fin, code_famille
            ),
            "en_service": counts["en_service"],
            "en_chomage": counts["en_chomage"],
            "en_panne": counts["en_panne"],
            "immobilise_base": counts["immobilise_base"],
            "en_reparation": counts["en_reparation"],
            "autres": counts["autres"],
            "alrem": counts["alrem"],
            "age_moyen": age_moyen,
        }

        maintenance_kpis = {
            "tamd": ratios["tmad"],
            "tam": ratios["tam"],
            "tip": ratios["tip"],
            "note": (
                "TMAD = (potentiel - heures panne - heures chômage) / potentiel ; "
                "TAM = heures service / (potentiel - heures panne) ; "
                "TIP = heures panne / potentiel."
            ),
            "en_panne": counts["en_panne"],
            "en_reparation": counts["en_reparation"],
            "taux_service": ratios["taux_utilisation"],
            "taux_chomage": ratios["taux_chomage"],
            # `taux_panne` is the hours-based panne rate; it is numerically
            # identical to `tip` by construction (both are heures_panne /
            # potentiel) and is kept because the v1 dashboard renders that name.
            "taux_panne": ratios["tip"],
            "disponibilite": ratios["disponibilite"],
            "potentiel_total": potentiel_total,
            "heures_service": heures_service,
            "heures_chomage": heures_chomage,
            "heures_panne": heures_panne,
        }

        financial_agg = pointages.aggregate(
            # ORDER MATTERS (see the note above): `ca_realise` *reads*
            # `montant_service` through a CASE, so the plain Sum of that same
            # field must come after it, never before.
            ca_realise=Coalesce(
                Sum(DashboardV2Service._ca_expr()),
                Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
            ),
            ca_potentiel=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("potentiel") * F("taux_location"),
                        output_field=DecimalField(max_digits=30, decimal_places=7),
                    )
                ),
                Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
            ),
            montant_service=_sum_montant("montant_service"),
            montant_chomage=_sum_montant("montant_chomage"),
            montant_panne=_sum_montant("montant_panne"),
        )
        fact_service = float(financial_agg["montant_service"])
        fact_chomage = float(financial_agg["montant_chomage"])
        fact_panne = float(financial_agg["montant_panne"])
        ca_realise = float(financial_agg["ca_realise"])
        ca_potentiel = float(financial_agg["ca_potentiel"])
        total_facture = ca_realise + fact_chomage + fact_panne
        total_regularisation = float(reg_total or 0)

        financial_kpis = {
            "totalFacture": total_facture,
            # What was actually billed for service: the stored amount when it
            # exists, the hours x tariff fallback otherwise.
            "caRealise": ca_realise,
            # Raw stored amount only (no fallback) — the "données saisies" view.
            "factService": fact_service,
            "factChomage": fact_chomage,
            "factPanne": fact_panne,
            # Signed: negative means the fleet billed MORE than its potential.
            "manqueAGagner": ca_potentiel - ca_realise,
            "caPotentiel": ca_potentiel,
            "totalRegularisation": total_regularisation,
            "marge": ca_realise - total_regularisation,
            # Positive = good (potential not reached), see the module docstring.
            "ecartCible": round(
                ((ca_potentiel - ca_realise) / ca_potentiel * 100)
                if ca_potentiel > 0
                else 0.0,
                1,
            ),
        }

        return {
            "globalKpis": global_kpis,
            "maintenanceKpis": maintenance_kpis,
            "financialKpis": financial_kpis,
            "filialeDistribution": filiale_distribution,
        }

    @staticmethod
    def get_situation(code_filiale=None, date_debut=None, date_fin=None, code_famille=None):
        date_debut, date_fin = DashboardV2Service._resolve_range(date_debut, date_fin)
        pointages = DashboardV2Service._pointage_base(
            code_filiale, date_debut, date_fin, code_famille
        )

        pointage_evolution = [
            {"mmaa": _iso(row["mmaa_month"]), **DashboardV2Service._raw_pointage(row)}
            for row in DashboardV2Service._grouped_by_period(
                pointages, DashboardV2Service._pointage_aggregates()
            )
        ]

        famille_rows = (
            pointages.annotate(
                code_famille=F(
                    "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille"
                ),
                libelle_famille=F(
                    "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille"
                ),
                code_sous_famille=F(
                    "affectation_id__code_materiel__code_sous_famille_materiel__code_sous_famille"
                ),
                libelle_sous_famille=F(
                    "affectation_id__code_materiel__code_sous_famille_materiel__libelle_sous_famille"
                ),
            )
            .values(
                "code_famille",
                "libelle_famille",
                "code_sous_famille",
                "libelle_sous_famille",
            )
            .annotate(count=Count("id"), **DashboardV2Service._pointage_aggregates())
            .order_by("code_famille")
        )
        famille_distribution = [
            {
                "code_famille": row["code_famille"],
                "libelle_famille": row["libelle_famille"],
                "code_sous_famille": row["code_sous_famille"],
                "libelle_sous_famille": row["libelle_sous_famille"],
                "count": row["count"],
                "heures_service": float(row["heures_service"]),
                "heures_chomage": float(row["heures_chomage"]),
                "heures_panne": float(row["heures_panne"]),
                "potentiel": float(row["potentiel"]),
            }
            for row in famille_rows
        ]

        return {
            "situationDistribution": DashboardV2Service._situation_distribution(
                code_filiale, date_fin, code_famille
            ),
            "pointageEvolution": pointage_evolution,
            "familleDistribution": famille_distribution,
        }

    @staticmethod
    def get_disponibilite(
        code_filiale=None, date_debut=None, date_fin=None, code_famille=None, niveau=NIVEAU_DEFAUT
    ):
        date_debut, date_fin = DashboardV2Service._resolve_range(date_debut, date_fin)
        pointages = DashboardV2Service._pointage_base(
            code_filiale, date_debut, date_fin, code_famille
        )
        evolution, breakdown = DashboardV2Service._ratio_series(pointages, niveau)
        return {"evolution": evolution, "breakdown": breakdown}

    @staticmethod
    def get_maintenance(
        code_filiale=None, date_debut=None, date_fin=None, code_famille=None, niveau=NIVEAU_DEFAUT
    ):
        date_debut, date_fin = DashboardV2Service._resolve_range(date_debut, date_fin)
        pointages = DashboardV2Service._pointage_base(
            code_filiale, date_debut, date_fin, code_famille
        )

        # MTBF / MTTR / CoutPanne: one `.annotate()` pass each (Sum + Count with a
        # `Q` filter), replacing v1's two-query + Python-merge pattern.
        return {
            "mtbf": DashboardV2Service._maintenance_series(
                pointages,
                niveau,
                DashboardV2Service._mtbf_aggregates,
                "heures_service",
                "nombre_pannes",
                "mtbf",
            ),
            "mttr": DashboardV2Service._maintenance_series(
                pointages,
                niveau,
                DashboardV2Service._mttr_aggregates,
                "heures_panne",
                "interventions_correctives",
                "mttr",
            ),
            "coutPanne": DashboardV2Service._cout_panne_series(pointages, niveau),
        }

    # NOTE ON ORDERING: within a single `.annotate()` group, a `Sum` and a
    # filtered `Count` that reference the *same* field cannot be annotated in an
    # arbitrary order — Django leaks the resolved aggregate into the other
    # expression and the query is rejected ("is an aggregate" / "aggregate
    # functions are not allowed in FILTER"). The dicts below are therefore
    # ordered explicitly; do not reorder them without re-testing.

    @staticmethod
    def _mtbf_aggregates():
        return {
            "nombre_pannes": _count(Q(heures_panne__gt=0)),
            "heures_service": _sum("heures_service"),
        }

    @staticmethod
    def _mttr_aggregates():
        return {
            "interventions_correctives": _count(Q(heures_panne__gt=0)),
            "heures_panne": _sum("heures_panne"),
        }

    @staticmethod
    def _cout_panne_aggregates():
        # ORDER MATTERS (see the note above): `cout_panne` reads
        # `taux_location`, which the two filtered counts also reference, so it
        # comes *first* (opposite of MTTR, where the filtered Count has to come
        # first); and the filtered Sum of `heures_panne` must come *before* the
        # plain Sum of the same field.
        return {
            "cout_panne": Coalesce(
                Sum(DashboardV2Service._cout_panne_expr()),
                Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
            ),
            # Hours of the records that DO carry a tariff: the correct
            # denominator of the weighted hourly rate (rows with a NULL
            # `taux_location` contribute hours but zero cost and would bias it
            # low).
            "heures_panne_avec_tarif": Coalesce(
                Sum(
                    "heures_panne",
                    filter=Q(taux_location__isnull=False),
                ),
                Value(0, output_field=DecimalField(max_digits=18, decimal_places=1)),
            ),
            "heures_panne": _sum("heures_panne"),
            "records_with_tarif": _count(Q(taux_location__isnull=False)),
            "records_without_tarif": _count(Q(taux_location__isnull=True)),
        }

    @staticmethod
    def _maintenance_series(qs, niveau, aggregates_factory, numerator, denominator, ratio_name):
        """Build {evolution, breakdown} for a (total / count) maintenance ratio."""
        rows, value_field, label_field = DashboardV2Service._grouped(
            qs, niveau, aggregates_factory()
        )

        def build(row):
            total = float(row[numerator] or 0)
            count = int(row[denominator] or 0)
            payload = {numerator: total, denominator: count}
            payload[ratio_name] = round(total / count, 2) if count > 0 else None
            return payload

        buckets = {}
        for row in rows:
            period = row["mmaa_month"]
            bucket = buckets.setdefault(period, {numerator: 0.0, denominator: 0})
            bucket[numerator] += float(row[numerator] or 0)
            bucket[denominator] += int(row[denominator] or 0)

        evolution = [
            {
                "mmaa": _iso(period),
                **build(bucket),
            }
            for period in sorted(buckets, key=lambda m: (m is None, m))
        ]

        entities = {}
        for row in rows:
            code = row[value_field]
            bucket = entities.setdefault(
                code,
                {
                    "libelle": row[label_field],
                    numerator: 0.0,
                    denominator: 0,
                },
            )
            if bucket["libelle"] is None:
                bucket["libelle"] = row[label_field]
            bucket[numerator] += float(row[numerator] or 0)
            bucket[denominator] += int(row[denominator] or 0)

        breakdown = [
            {"code": code, "libelle": bucket["libelle"] or code, **build(bucket)}
            for code, bucket in sorted(entities.items(), key=lambda kv: (kv[0] is None, kv[0]))
        ]

        return {"evolution": evolution, "breakdown": breakdown}

    @staticmethod
    def _cout_panne_series(qs, niveau):
        rows, value_field, label_field = DashboardV2Service._grouped(
            qs, niveau, DashboardV2Service._cout_panne_aggregates()
        )

        def build(row):
            return {
                "heures_panne": float(row["heures_panne"] or 0),
                "heures_panne_avec_tarif": float(row["heures_panne_avec_tarif"] or 0),
                "cout_panne": float(row["cout_panne"] or 0),
                "records_with_tarif": int(row["records_with_tarif"] or 0),
                "records_without_tarif": int(row["records_without_tarif"] or 0),
            }

        buckets = {}
        for row in rows:
            period = row["mmaa_month"]
            bucket = buckets.setdefault(
                period,
                {
                    "heures_panne": 0.0,
                    "heures_panne_avec_tarif": 0.0,
                    "cout_panne": 0.0,
                    "records_with_tarif": 0,
                    "records_without_tarif": 0,
                },
            )
            for field in bucket:
                bucket[field] += float(row[field] or 0)

        evolution = [
            {"mmaa": _iso(period), **build(bucket)}
            for period in sorted(buckets, key=lambda m: (m is None, m))
        ]

        entities = {}
        for row in rows:
            code = row[value_field]
            bucket = entities.setdefault(
                code,
                {
                    "libelle": row[label_field],
                    "heures_panne": 0.0,
                    "heures_panne_avec_tarif": 0.0,
                    "cout_panne": 0.0,
                    "records_with_tarif": 0,
                    "records_without_tarif": 0,
                },
            )
            if bucket["libelle"] is None:
                bucket["libelle"] = row[label_field]
            for field in bucket:
                if field == "libelle":
                    continue
                bucket[field] += float(row[field] or 0)

        breakdown = [
            {"code": code, "libelle": bucket["libelle"] or code, **build(bucket)}
            for code, bucket in sorted(entities.items(), key=lambda kv: (kv[0] is None, kv[0]))
        ]

        return {"evolution": evolution, "breakdown": breakdown}

    @staticmethod
    def get_rendement(
        code_filiale=None, date_debut=None, date_fin=None, code_famille=None, niveau=NIVEAU_DEFAUT
    ):
        date_debut, date_fin = DashboardV2Service._resolve_range(date_debut, date_fin)
        pointages = DashboardV2Service._pointage_base(
            code_filiale, date_debut, date_fin, code_famille
        )

        # ONE query feeds the whole endpoint: the rows are grouped by
        # (month, niveau-entity) exactly like `/disponibilite`, then folded
        # twice — per month (evolution) and per entity (breakdown).
        evolution, breakdown = DashboardV2Service._ratio_series(pointages, niveau)

        # `pointageEvolution` and `rendementEvolution` are the *same* series:
        # disponibilite, taux_utilisation and rendement are all derived from
        # the very same (potentiel, heures) tuples, so the previous two
        # identical arrays were the honest shape of the data. The entity view
        # now comes from this endpoint (niveau-aware) instead of a second
        # `/disponibilite` round-trip.
        return {
            "pointageEvolution": evolution,
            "rendementEvolution": evolution,
            "breakdown": breakdown,
        }

    @staticmethod
    def get_finances(
        code_filiale=None, date_debut=None, date_fin=None, code_famille=None, niveau=NIVEAU_DEFAUT
    ):
        date_debut, date_fin = DashboardV2Service._resolve_range(date_debut, date_fin)
        pointages = DashboardV2Service._pointage_base(
            code_filiale, date_debut, date_fin, code_famille
        )

        ca_evolution, ca_breakdown = DashboardV2Service._ca_series(pointages, niveau)

        # One niveau-aware ratio query feeds both taux d'utilisation and taux de chomage.
        ratio_evolution, ratio_breakdown = DashboardV2Service._ratio_series(pointages, niveau)

        taux_utilisation_evolution = DashboardV2Service._project(
            ratio_evolution, "heures_service", "potentiel", "taux_utilisation", keys=("mmaa",)
        )
        taux_utilisation_breakdown = DashboardV2Service._project(
            ratio_breakdown, "heures_service", "potentiel", "taux_utilisation"
        )
        taux_chomage_evolution = DashboardV2Service._project(
            ratio_evolution, "heures_chomage", "potentiel", "taux_chomage", keys=("mmaa",)
        )
        taux_chomage_breakdown = DashboardV2Service._project(
            ratio_breakdown, "heures_chomage", "potentiel", "taux_chomage"
        )

        rentabilite_evolution = DashboardV2Service._rentabilite_evolution(
            pointages, niveau, code_filiale, date_debut, date_fin, code_famille
        )
        rentabilite_ranking = DashboardV2Service._rentabilite_ranking(
            code_filiale, date_debut, date_fin, code_famille
        )

        taux_affectation_evolution, taux_affectation_breakdown, taux_affectation_global = (
            DashboardV2Service._taux_affectation_series(
                code_filiale, date_debut, date_fin, code_famille, niveau
            )
        )

        return {
            "caLocationInterne": {
                "evolution": ca_evolution,
                "breakdown": ca_breakdown,
            },
            "rentabilite": {
                "evolution": rentabilite_evolution,
                "ranking": rentabilite_ranking,
            },
            "tauxAffectation": {
                "evolution": taux_affectation_evolution,
                "breakdown": taux_affectation_breakdown,
                # Fleet-scoped rate: the breakdown is niveau-dependent (one row
                # per engin at `engin` niveau), so the frontend must never
                # re-derive the global rate by summing it.
                "global": taux_affectation_global,
            },
            "tauxAffectationGlobal": taux_affectation_global,
            "tauxUtilisation": {
                "evolution": taux_utilisation_evolution,
                "breakdown": taux_utilisation_breakdown,
            },
            "tauxChomage": {
                "evolution": taux_chomage_evolution,
                "breakdown": taux_chomage_breakdown,
            },
        }

    @staticmethod
    def get_filiale_stats(code_filiale=None, date_debut=None, date_fin=None, code_famille=None):
        """Per-filiale aggregation of parc, affectations, heures service and pointages.

        Single filiale axis: everything is grouped on the material's group
        (``code_materiel__code_filiale_g``), the same axis as ``_pointage_base``
        and ``_parc`` — the affectation's ``code_filiale_mere`` is a different
        (booking) axis and is not used here.

        When ``code_filiale`` is set the result collapses to a single row: the
        GROUPE sub-tab is a drill-down of the selected subsidiary. This is kept
        on purpose (it mirrors the parc/ratio tabs, which also narrow down).
        """
        filiales = Filiale.objects.filter(est_bloque=False)
        if code_filiale:
            filiales = filiales.filter(code_filiale=code_filiale)

        # Same default range as every other v2 endpoint (current month).
        date_debut, date_fin = DashboardV2Service._resolve_range(date_debut, date_fin)

        filiale_codes = [f.code_filiale for f in filiales]

        if not filiale_codes:
            return []

        gm_qs = Grand_Materiel.objects.filter(
            code_filiale_g__in=filiale_codes,
            est_bloque=False,
        )
        if code_famille:
            gm_qs = gm_qs.filter(
                code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )
        # Filter by type_affectation: exclude 06, 07, 08 and NON FOURNIE
        gm_qs = DashboardV2Service._filter_parc_by_type_affectation(gm_qs, date_fin)
        gm_stats = gm_qs.values("code_filiale_g").annotate(totalMateriel=Count("id"))

        aff_qs = Affectation_Materiel.objects.filter(
            code_materiel__code_filiale_g__in=filiale_codes,
            est_bloque=False,
            date_fin_affectation__isnull=True,
        )
        if code_famille:
            aff_qs = aff_qs.filter(
                code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )
        aff_stats = (
            aff_qs.values("code_materiel__code_filiale_g").annotate(
                totalAffectations=Count("id")
            )
        )

        pointage_qs = DashboardV2Service._pointage_base(
            code_filiale, date_debut, date_fin, code_famille
        ).filter(affectation_id__code_materiel__code_filiale_g__in=filiale_codes)

        pointage_stats = (
            pointage_qs
            .annotate(filiale_code=F("affectation_id__code_materiel__code_filiale_g"))
            .values("filiale_code")
            .annotate(
                totalHeuresService=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                totalPointages=Count("id"),
            )
        )

        gm_map = {row["code_filiale_g"]: row["totalMateriel"] for row in gm_stats}
        aff_map = {
            row["code_materiel__code_filiale_g"]: row["totalAffectations"]
            for row in aff_stats
        }
        pt_map = {row["filiale_code"]: row for row in pointage_stats}

        filiale_dict = {f.code_filiale: f for f in filiales}

        return [
            {
                "code_filiale": code,
                "libelle_filiale": filiale_dict[code].libelle_filiale,
                "totalMateriel": gm_map.get(code, 0),
                "totalAffectations": aff_map.get(code, 0),
                "totalHeuresService": float(pt_map.get(code, {}).get("totalHeuresService", 0)),
                "totalPointages": pt_map.get(code, {}).get("totalPointages", 0),
            }
            for code in filiale_codes
        ]

    @staticmethod
    def _ca_series(qs, niveau):
        """CA de location interne, evolution (monthly) + breakdown (by niveau)."""
        aggregates = {
            # `ca_total`, `ca_stocke` and `ca_calculee` all read
            # `montant_service` / `taux_location`, which the two counts below
            # reference: they must be annotated first. See the ordering note
            # above.
            "ca_total": Coalesce(
                Sum(DashboardV2Service._ca_expr()),
                Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
            ),
            # The two halves of `ca_total`, as *amounts* (the frontend used to
            # plot the record COUNTS and label them "CA stocké / CA calculé").
            "ca_stocke": Coalesce(
                Sum("montant_service"),
                Value(0, output_field=DecimalField(max_digits=20, decimal_places=7)),
            ),
            "ca_calculee": Coalesce(
                Sum(
                    ExpressionWrapper(
                        Case(
                            When(
                                montant_service__isnull=True,
                                taux_location__isnull=False,
                                then=F("heures_service") * F("taux_location"),
                            ),
                            default=Value(
                                0, output_field=DecimalField(max_digits=30, decimal_places=7)
                            ),
                            output_field=DecimalField(max_digits=30, decimal_places=7),
                        ),
                        output_field=DecimalField(max_digits=30, decimal_places=7),
                    )
                ),
                Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
            ),
            "records_with_montant": _count(Q(montant_service__isnull=False)),
            "records_without_montant": _count(Q(montant_service__isnull=True)),
        }
        rows, value_field, label_field = DashboardV2Service._grouped(
            qs, niveau, aggregates
        )

        def blank():
            return {
                "ca_total": 0.0,
                "ca_stocke": 0.0,
                "ca_calculee": 0.0,
                "records_with_montant": 0,
                "records_without_montant": 0,
            }

        def build(row):
            return {
                "ca_total": float(row["ca_total"] or 0),
                "ca_stocke": float(row["ca_stocke"] or 0),
                "ca_calculee": float(row["ca_calculee"] or 0),
                "records_with_montant": int(row["records_with_montant"] or 0),
                "records_without_montant": int(row["records_without_montant"] or 0),
            }

        buckets = {}
        for row in rows:
            bucket = buckets.setdefault(row["mmaa_month"], blank())
            for field in bucket:
                bucket[field] += float(row[field] or 0)

        evolution = [
            {"mmaa": _iso(period), **build(bucket)}
            for period in sorted(buckets, key=lambda m: (m is None, m))
        ]

        entities = {}
        for row in rows:
            code = row[value_field]
            bucket = entities.setdefault(
                code, {"libelle": row[label_field], **blank()}
            )
            if bucket["libelle"] is None:
                bucket["libelle"] = row[label_field]
            for field in blank():
                bucket[field] += float(row[field] or 0)

        breakdown = [
            {"code": code, "libelle": bucket["libelle"] or code, **build(bucket)}
            for code, bucket in sorted(entities.items(), key=lambda kv: (kv[0] is None, kv[0]))
        ]

        return evolution, breakdown

    @staticmethod
    def _rentabilite_entities(qs, niveau, reg_qs, period_expr):
        """{(period, code): {chiffre_affaires, regularisation, marge, libelle}}.

        La regularisation est proratee sur les heures de service de l'entite
        au sein de son **propre (site, periode)** — pas sur les heures de tous
        les sites confondus: le denominateur doit etre `heures_service` du
        site, sinon chaque site se voit imputer une fraction des heures des
        autres et la somme des regularisations allouees ne redonne pas le
        total du site.
        """
        value_field, label_field = DashboardV2Service._niveau_grouping(niveau)

        rows = (
            qs.annotate(period=period_expr("mmaa"))
            .values("period", value_field, label_field, "affectation_id__code_site")
            .annotate(
                chiffre_affaires=Coalesce(
                    Sum(DashboardV2Service._ca_expr()),
                    Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
                ),
                heures_service=_sum("heures_service"),
            )
        )

        heures_par_site_periode = defaultdict(float)
        for row in rows:
            heures_par_site_periode[
                (row["affectation_id__code_site"], row["period"])
            ] += float(row["heures_service"] or 0)

        reg_map = {}
        # `code_site__code_site` (not `code_site`): the Site FK uses
        # `to_field="code_site"`, so `values("code_site")` would return the
        # row PK while the pointage side yields the site *code* — the two keys
        # would never match and every regularisation would allocate 0.
        for row in reg_qs.annotate(period=period_expr("mmaa")).values(
            "code_site__code_site", "period"
        ).annotate(total=_sum_montant("montant_regularisation")):
            reg_map[(row["code_site__code_site"], row["period"])] = float(row["total"] or 0)

        entities = {}
        for row in rows:
            key = (row["period"], row[value_field])
            entry = entities.setdefault(
                key,
                {
                    "libelle": row[label_field],
                    "chiffre_affaires": 0.0,
                    "regularisation": 0.0,
                },
            )
            if entry["libelle"] is None:
                entry["libelle"] = row[label_field]
            entry["chiffre_affaires"] += float(row["chiffre_affaires"] or 0)

            site = row["affectation_id__code_site"]
            site_key = (site, row["period"])
            total_heures = heures_par_site_periode.get(site_key, 0.0)
            if total_heures > 0:
                entry["regularisation"] += reg_map.get(site_key, 0.0) * (
                    float(row["heures_service"] or 0) / total_heures
                )

        for entry in entities.values():
            entry["marge"] = entry["chiffre_affaires"] - entry["regularisation"]
        return entities

    @staticmethod
    def _rentabilite_evolution(qs, niveau, code_filiale, date_debut, date_fin, code_famille):
        reg_qs = DashboardV2Service._regularisation(
            code_filiale, date_debut, date_fin, code_famille
        )
        entities = DashboardV2Service._rentabilite_entities(qs, niveau, reg_qs, TruncQuarter)

        buckets = defaultdict(
            lambda: {"chiffre_affaires": 0.0, "regularisation": 0.0, "marge": 0.0}
        )
        for (period, _code), entry in entities.items():
            bucket = buckets[period]
            for field in bucket:
                bucket[field] += entry[field]

        return [
            {
                "quarter": _iso(period),
                "chiffre_affaires": round(bucket["chiffre_affaires"], 2),
                "regularisation": round(bucket["regularisation"], 2),
                "marge": round(bucket["marge"], 2),
            }
            for period, bucket in sorted(buckets.items(), key=lambda kv: (kv[0] is None, kv[0]))
        ]

    @staticmethod
    def _rentabilite_ranking(code_filiale, date_debut, date_fin, code_famille):
        """Ranking par engin, mis en cache 5 min (independant du niveau)."""
        cache_key = "dashboard_v2:rentabilite:%s:%s:%s:%s" % (
            code_filiale or "all",
            date_debut,
            date_fin,
            code_famille or "all",
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        pointages = DashboardV2Service._pointage_base(
            code_filiale, date_debut, date_fin, code_famille
        )
        reg_qs = DashboardV2Service._regularisation(
            code_filiale, date_debut, date_fin, code_famille
        )
        entities = DashboardV2Service._rentabilite_entities(
            pointages, NIVEAU_DEFAUT, reg_qs, TruncMonth
        )

        # The ranking is engine-scoped, so the famille / filiale of each code
        # only have to be resolved once (the ranking table renders them).
        labels = {
            row["code_materiel"]: row
            for row in Grand_Materiel.objects.filter(
                code_materiel__in={code for (_period, code) in entities}
            )
            .values(
                "code_materiel",
                "code_sous_famille_materiel__code_famille_materiel__libelle_famille",
                "code_filiale_g__libelle_filiale",
            )
        }

        merged = {}
        for (_period, code), entry in entities.items():
            merged.setdefault(
                code,
                {
                    "code_materiel": code,
                    "designation": entry["libelle"],
                    "chiffre_affaires": 0.0,
                    "regularisation": 0.0,
                },
            )
            target = merged[code]
            if target["designation"] is None:
                target["designation"] = entry["libelle"]
            target["chiffre_affaires"] += entry["chiffre_affaires"]
            target["regularisation"] += entry["regularisation"]

        ranking = [
            {
                "code_materiel": item["code_materiel"],
                "designation": item["designation"] or item["code_materiel"],
                "libelle_famille": (labels.get(item["code_materiel"]) or {}).get(
                    "code_sous_famille_materiel__code_famille_materiel__libelle_famille"
                )
                or "—",
                "libelle_filiale": (labels.get(item["code_materiel"]) or {}).get(
                    "code_filiale_g__libelle_filiale"
                )
                or "—",
                "chiffre_affaires": round(item["chiffre_affaires"], 2),
                "regularisation": round(item["regularisation"], 2),
                "marge": round(item["chiffre_affaires"] - item["regularisation"], 2),
            }
            for item in merged.values()
        ]
        ranking.sort(key=lambda row: row["marge"], reverse=True)

        cache.set(cache_key, ranking, RENTABILITE_CACHE_TTL)
        return ranking

    @staticmethod
    def _taux_affectation_series(code_filiale, date_debut, date_fin, code_famille, niveau):
        """Return ``(evolution, breakdown, global)`` for the affectation rate.

        * ``evolution`` is a FLOW: the affectations *created* in the month
          (``date_affectation``), closed or not — restricting it to the still
          open ones used to make historical months shrink to zero.
        * the ``parc_total`` of every row is a STOCK: the parc at ``date_fin``.
        * ``global`` is the fleet-level rate, so the frontend never has to sum
          a niveau-dependent breakdown.
        """
        # Filiale axis: the material's group (`code_filiale_g`), same as
        # `_pointage_base` and `_parc` — `code_filiale_mere` is the booking
        # subsidiary of the affectation, a different axis.
        def _affectations():
            qs = Affectation_Materiel.objects.filter(est_bloque=False)
            if code_filiale:
                qs = qs.filter(code_materiel__code_filiale_g=code_filiale)
            if code_famille:
                qs = qs.filter(
                    code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
                )
            return qs

        active = _affectations().filter(date_fin_affectation__isnull=True)

        parc = DashboardV2Service._parc(code_filiale, code_famille, date_fin=date_fin)
        parc_total = parc.count()
        engins_affectes_global = (
            active.filter(code_materiel__in=parc.values("code_materiel"))
            .values("code_materiel")
            .distinct()
            .count()
        )

        # Evolution mensuelle des mises en affectation (flow, not stock).
        evolution_rows = (
            _affectations()
            .filter(date_affectation__date__range=(date_debut, date_fin))
            .annotate(mmaa_month=TruncMonth("date_affectation"))
            .values("mmaa_month")
            .annotate(engins_affectes=Count("code_materiel", distinct=True))
            .order_by("mmaa_month")
        )
        evolution = [
            {
                "mmaa": _iso(row["mmaa_month"]),
                "engins_affectes": row["engins_affectes"],
                "parc_total": parc_total,
                "taux_affectation": round(
                    (row["engins_affectes"] / parc_total * 100) if parc_total else 0.0, 1
                ),
            }
            for row in evolution_rows
        ]

        if niveau == "chantier":
            # The parc has no site dimension: attributing a share of the fleet
            # to each chantier would make every row a ratio of the *whole* parc
            # and `Σparc_total` would equal parc × nb_chantiers. A per-chantier
            # rate is therefore not meaningful here, and the endpoint returns
            # the fleet-level row once — `Σparc_total` stays == parc.count().
            breakdown = [
                {
                    "code": "TOTAL",
                    "libelle": "Ensemble du parc",
                    "parc_total": parc_total,
                    "engins_affectes": engins_affectes_global,
                    "taux_affectation": round(
                        (engins_affectes_global / parc_total * 100)
                        if parc_total
                        else 0.0,
                        1,
                    ),
                }
            ]
        else:
            value_field, label_field = DashboardV2Service._niveau_grouping(niveau, "parc")
            rows = (
                parc.annotate(
                    has_active_affectation=Exists(
                        active.filter(code_materiel=OuterRef("code_materiel"))
                    )
                )
                .values(value_field, label_field)
                .annotate(
                    parc_total=Count("id"),
                    engins_affectes=Count("id", filter=Q(has_active_affectation=True)),
                )
            )
            breakdown = []
            for row in rows:
                row_parc = int(row["parc_total"] or 0)
                row_affectes = int(row["engins_affectes"] or 0)
                breakdown.append(
                    {
                        "code": row[value_field],
                        "libelle": row[label_field] or row[value_field],
                        "parc_total": row_parc,
                        "engins_affectes": row_affectes,
                        "taux_affectation": round(
                            (row_affectes / row_parc * 100) if row_parc else 0.0, 1
                        ),
                    }
                )
            breakdown.sort(key=lambda row: (row["code"] is None, row["code"]))

        global_row = {
            "parc_total": parc_total,
            "engins_affectes": engins_affectes_global,
            "taux_affectation": round(
                (engins_affectes_global / parc_total * 100) if parc_total else 0.0, 1
            ),
        }

        return evolution, breakdown, global_row

    @staticmethod
    def get_filiales():
        return [
            {"value": row["code_filiale"], "label": row["libelle_filiale"]}
            for row in Filiale.objects.filter(est_bloque=False)
            .values("code_filiale", "libelle_filiale")
            .order_by("code_filiale")
        ]

    @staticmethod
    def get_familles():
        return [
            {"value": row["code_famille"], "label": row["libelle_famille"]}
            for row in Famille_Materiel.objects.filter(est_bloque=False)
            .values("code_famille", "libelle_famille")
            .order_by("code_famille")
        ]
