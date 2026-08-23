from datetime import date, timedelta
from collections import defaultdict

from django.db.models import (
    F,
    Q,
    Count,
    Sum,
    Avg,
    Case,
    When,
    IntegerField,
    DecimalField,
    ExpressionWrapper,
    Exists,
    OuterRef,
    Value,
    Window,
)
from django.db.models.functions import (
    Lead,
    Cast,
    Greatest,
    RowNumber,
    TruncMonth,
    Coalesce,
)
from django.utils import timezone

from api.models import (
    Grand_Materiel,
    Affectation_Materiel,
    Situation_Materiel,
    Type_Situation,
    Pointage,
    Regularisation_GM,
    Filiale,
    Journal,
    Sous_Famille_Materiel,
    Famille_Materiel,
    Categorie_GM,
)
from api.services.analyse_qunatitaive import AnalyseQuantitativeResume
from api.services.analyse_exploitation import AnalyseExploitationResume


class DashboardService:

    @staticmethod
    def _get_default_date_range():
        today = date.today()
        date_debut = today - timedelta(days=365)
        return date_debut, today

    @staticmethod
    def get_dashboard(
        code_filiale=None,
        date_debut=None,
        date_fin=None,
        code_famille=None,
        periode=None,
        mode="standard",
    ):
        if not date_debut or not date_fin:
            default_debut, default_fin = DashboardService._get_default_date_range()
            date_debut = date_debut or default_debut
            date_fin = date_fin or default_fin

        overview = DashboardService._get_overview(code_filiale)
        situation_distribution = DashboardService._get_situation_distribution(
            code_filiale, date_debut, date_fin
        )
        pointage_evolution = DashboardService._get_pointage_evolution(
            code_filiale, date_debut, date_fin
        )
        filiale_stats = DashboardService._get_filiale_stats(code_filiale)
        alerts = DashboardService._get_alerts(code_filiale)
        recent_activity = DashboardService._get_recent_activity()

        famille_distribution = DashboardService._get_famille_distribution(
            code_filiale, date_debut, date_fin, code_famille
        )
        trends = DashboardService._get_trends(
            code_filiale, date_debut, date_fin, code_famille
        )
        financial_kpis = DashboardService._get_financial_kpis(
            code_filiale, date_debut, date_fin, code_famille
        )
        maintenance_kpis = DashboardService._get_maintenance_kpis(
            code_filiale, date_debut, date_fin, code_famille
        )
        material_details = DashboardService._get_material_details(
            code_filiale, date_debut, date_fin, code_famille, page=1, page_size=50
        )

        result = {
            "overview": overview,
            "situationDistribution": situation_distribution,
            "pointageEvolution": pointage_evolution,
            "filialeStats": filiale_stats,
            "alerts": alerts,
            "recentActivity": recent_activity,
            "familleDistribution": famille_distribution,
            "trends": trends,
            "financialKpis": financial_kpis,
            "maintenanceKpis": maintenance_kpis,
            "materialDetails": material_details,
            "filters": {
                "code_filiale": code_filiale,
                "date_debut": date_debut,
                "date_fin": date_fin,
                "code_famille": code_famille,
                "periode": periode,
                "mode": mode,
            },
        }

        if code_filiale:
            try:
                quantitative_resume = AnalyseQuantitativeResume.get_situations_resume(
                    code_filiale=code_filiale,
                    date_debut=date_debut,
                    date_fin=date_fin,
                )
                result["quantitativeResume"] = quantitative_resume
            except Exception:
                result["quantitativeResume"] = None

            try:
                exploitation_resume = AnalyseExploitationResume.get_pointages_resume(
                    code_filiale=code_filiale,
                    date_debut=date_debut,
                    date_fin=date_fin,
                )
                result["exploitationResume"] = exploitation_resume
            except Exception:
                result["exploitationResume"] = None

        return result

    @staticmethod
    def _get_overview(code_filiale):
        gm_qs = Grand_Materiel.objects.all()
        aff_qs = Affectation_Materiel.objects.all()
        pointage_qs = Pointage.objects.all()
        reg_qs = Regularisation_GM.objects.all()

        if code_filiale:
            gm_qs = gm_qs.filter(code_filiale_g=code_filiale)
            aff_qs = aff_qs.filter(code_filiale_mere=code_filiale)
            pointage_qs = pointage_qs.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )
            reg_qs = reg_qs.filter(code_site__code_filiale=code_filiale)

        total_materiel = gm_qs.count()
        materiel_actif = gm_qs.filter(est_bloque=False).count()
        materiel_inactif = gm_qs.filter(est_bloque=True).count()

        active_affectations = Affectation_Materiel.objects.filter(
            est_bloque=False,
            date_fin_affectation__isnull=True,
        )
        if code_filiale:
            active_affectations = active_affectations.filter(code_filiale_mere=code_filiale)

        materiel_affecte = Grand_Materiel.objects.filter(
            est_bloque=False,
        ).annotate(
            has_active_affectation=Exists(
                active_affectations.filter(code_materiel=OuterRef("code_materiel"))
            )
        ).filter(has_active_affectation=True)

        if code_filiale:
            materiel_affecte = materiel_affecte.filter(code_filiale_g=code_filiale)

        materiel_affecte_count = materiel_affecte.count()

        pointage_agg = pointage_qs.aggregate(
            total_heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            total_heures_chomage=Coalesce(Sum("heures_chomage"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            total_heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            total_montant_service=Coalesce(Sum("montant_service"), Value(0, output_field=DecimalField(max_digits=20, decimal_places=7))),
            total_montant_chomage=Coalesce(Sum("montant_chomage"), Value(0, output_field=DecimalField(max_digits=20, decimal_places=7))),
            total_montant_panne=Coalesce(Sum("montant_panne"), Value(0, output_field=DecimalField(max_digits=20, decimal_places=7))),
            total_pointages=Count("id"),
        )

        reg_agg = reg_qs.aggregate(
            total_regularisation=Coalesce(Sum("montant_regularisation"), Value(0, output_field=DecimalField(max_digits=20, decimal_places=4)))
        )

        return {
            "totalMateriel": total_materiel,
            "materielActif": materiel_actif,
            "materielInactif": materiel_inactif,
            "materielAffecte": materiel_affecte_count,
            "materielNonAffecte": materiel_actif - materiel_affecte_count,
            "totalAffectations": aff_qs.count(),
            "affectationsActives": active_affectations.count(),
            "totalPointages": pointage_agg["total_pointages"],
            "totalHeuresService": float(pointage_agg["total_heures_service"]),
            "totalHeuresChomage": float(pointage_agg["total_heures_chomage"]),
            "totalHeuresPanne": float(pointage_agg["total_heures_panne"]),
            "totalMontantService": float(pointage_agg["total_montant_service"]),
            "totalMontantChomage": float(pointage_agg["total_montant_chomage"]),
            "totalMontantPanne": float(pointage_agg["total_montant_panne"]),
            "totalRegularisation": float(reg_agg["total_regularisation"]),
        }

    @staticmethod
    def _get_situation_distribution(code_filiale, date_debut, date_fin):
        situations = Situation_Materiel.objects.filter(
            date_situation__date__lte=date_fin,
            est_bloque=False,
        )

        if code_filiale:
            situations = situations.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        latest_ids = list(
            situations.annotate(
                rn=Window(
                    expression=RowNumber(),
                    partition_by=[F("affectation_id__code_materiel")],
                    order_by=[F("date_situation").desc(), F("id").desc()],
                )
            )
            .filter(rn=1)
            .values_list("id", flat=True)
        )

        distribution = (
            Situation_Materiel.objects.filter(id__in=latest_ids)
            .values(
                "type_situation_id__code_type_situation",
                "type_situation_id__libelle_type_situation",
            )
            .annotate(count=Count("id"))
            .order_by("type_situation_id__code_type_situation")
        )

        return [
            {
                "code_type_situation": row["type_situation_id__code_type_situation"],
                "libelle_type_situation": row["type_situation_id__libelle_type_situation"],
                "count": row["count"],
            }
            for row in distribution
        ]

    @staticmethod
    def _get_pointage_evolution(code_filiale, date_debut, date_fin):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        evolution = (
            pointages.annotate(month=TruncMonth("mmaa"))
            .values("month")
            .annotate(
                heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_chomage=Coalesce(Sum("heures_chomage"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            )
            .order_by("month")
        )

        return [
            {
                "mmaa": row["month"].strftime("%Y-%m-%d") if row["month"] else None,
                "heures_service": float(row["heures_service"]),
                "heures_chomage": float(row["heures_chomage"]),
                "heures_panne": float(row["heures_panne"]),
            }
            for row in evolution
        ]

    @staticmethod
    def _get_filiale_stats(code_filiale):
        filiales = Filiale.objects.filter(est_bloque=False)
        if code_filiale:
            filiales = filiales.filter(code_filiale=code_filiale)

        filiale_codes = [f.code_filiale for f in filiales]

        if not filiale_codes:
            return []

        gm_stats = (
            Grand_Materiel.objects.filter(
                code_filiale_g__in=filiale_codes,
                est_bloque=False,
            )
            .values("code_filiale_g")
            .annotate(totalMateriel=Count("id"))
        )

        aff_stats = (
            Affectation_Materiel.objects.filter(
                code_filiale_mere__in=filiale_codes,
                est_bloque=False,
                date_fin_affectation__isnull=True,
            )
            .values("code_filiale_mere")
            .annotate(totalAffectations=Count("id"))
        )

        pointage_stats = (
            Pointage.objects.filter(
                est_bloque=False,
                affectation_id__code_materiel__code_filiale_g__in=filiale_codes,
            )
            .annotate(filiale_code=F("affectation_id__code_materiel__code_filiale_g"))
            .values("filiale_code")
            .annotate(
                totalHeuresService=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                totalPointages=Count("id"),
            )
        )

        gm_map = {row["code_filiale_g"]: row["totalMateriel"] for row in gm_stats}
        aff_map = {row["code_filiale_mere"]: row["totalAffectations"] for row in aff_stats}
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
    def _get_famille_distribution(code_filiale, date_debut, date_fin, code_famille=None):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
            affectation_id__prenable=True,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        qs = (
            pointages
            .annotate(
                code_famille=F("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille"),
                libelle_famille=F("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille"),
                code_sous_famille=F("affectation_id__code_materiel__code_sous_famille_materiel__code_sous_famille"),
                libelle_sous_famille=F("affectation_id__code_materiel__code_sous_famille_materiel__libelle_sous_famille"),
            )
            .values("code_famille", "libelle_famille", "code_sous_famille", "libelle_sous_famille")
            .annotate(
                count=Count("id"),
                heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_chomage=Coalesce(Sum("heures_chomage"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            )
            .order_by("code_famille")
        )

        if code_famille:
            qs = qs.filter(code_famille=code_famille)

        return [
            {
                "code_famille": row["code_famille"],
                "libelle_famille": row["libelle_famille"],
                "code_sous_famille": row["code_sous_famille"],
                "libelle_sous_famille": row["libelle_sous_famille"],
                "count": row["count"],
                "heures_service": float(row["heures_service"]),
                "heures_chomage": float(row["heures_chomage"]),
                "heures_panne": float(row["heures_panne"]),
            }
            for row in qs
        ]

    @staticmethod
    def _get_trends(code_filiale, date_debut, date_fin, code_famille=None):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
            affectation_id__prenable=True,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        if code_famille:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        evolution = (
            pointages.annotate(month=TruncMonth("mmaa"))
            .values("month")
            .annotate(
                heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_chomage=Coalesce(Sum("heures_chomage"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                montant_service=Coalesce(Sum("montant_service"), Value(0, output_field=DecimalField(max_digits=20, decimal_places=7))),
                montant_chomage=Coalesce(Sum("montant_chomage"), Value(0, output_field=DecimalField(max_digits=20, decimal_places=7))),
                montant_panne=Coalesce(Sum("montant_panne"), Value(0, output_field=DecimalField(max_digits=20, decimal_places=7))),
            )
            .order_by("month")
        )

        return [
            {
                "mmaa": row["month"].strftime("%Y-%m-%d") if row["month"] else None,
                "heures_service": float(row["heures_service"]),
                "heures_chomage": float(row["heures_chomage"]),
                "heures_panne": float(row["heures_panne"]),
                "montant_service": float(row["montant_service"]),
                "montant_chomage": float(row["montant_chomage"]),
                "montant_panne": float(row["montant_panne"]),
            }
            for row in evolution
        ]

    @staticmethod
    def _get_financial_kpis(code_filiale, date_debut, date_fin, code_famille=None):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
            affectation_id__prenable=True,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        if code_famille:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        pointage_agg = pointages.aggregate(
            total_montant_service=Coalesce(Sum("montant_service"), Value(0, output_field=DecimalField(max_digits=20, decimal_places=7))),
            total_montant_chomage=Coalesce(Sum("montant_chomage"), Value(0, output_field=DecimalField(max_digits=20, decimal_places=7))),
            total_montant_panne=Coalesce(Sum("montant_panne"), Value(0, output_field=DecimalField(max_digits=20, decimal_places=7))),
        )

        reg_qs = Regularisation_GM.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )
        if code_filiale:
            reg_qs = reg_qs.filter(code_site__code_filiale=code_filiale)

        reg_agg = reg_qs.aggregate(
            total_regularisation=Coalesce(Sum("montant_regularisation"), Value(0, output_field=DecimalField(max_digits=20, decimal_places=4)))
        )

        total_facture = float(pointage_agg["total_montant_service"]) + float(pointage_agg["total_montant_chomage"]) + float(pointage_agg["total_montant_panne"])
        fact_service = float(pointage_agg["total_montant_service"])

        return {
            "totalFacture": total_facture,
            "factService": fact_service,
            "totalRegularisation": float(reg_agg["total_regularisation"]),
            "marge": fact_service - float(reg_agg["total_regularisation"]),
        }

    @staticmethod
    def _get_maintenance_kpis(code_filiale, date_debut, date_fin, code_famille=None):
        return {
            "tamd": None,
            "tam": None,
            "tip": None,
            "note": "Maintenance KPIs require TMAD/TAM/TIP backend data not currently available.",
        }

    @staticmethod
    def _get_material_details(code_filiale, date_debut, date_fin, code_famille=None, page=1, page_size=50):
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

        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def _get_alerts(code_filiale):
        alerts = []

        gm_qs = Grand_Materiel.objects.filter(est_bloque=False)
        aff_qs = Affectation_Materiel.objects.filter(est_bloque=False)
        pointage_qs = Pointage.objects.filter(est_bloque=False)

        if code_filiale:
            gm_qs = gm_qs.filter(code_filiale_g=code_filiale)
            aff_qs = aff_qs.filter(code_filiale_mere=code_filiale)
            pointage_qs = pointage_qs.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        active_affectations = Affectation_Materiel.objects.filter(
            est_bloque=False,
            date_fin_affectation__isnull=True,
        )
        if code_filiale:
            active_affectations = active_affectations.filter(code_filiale_mere=code_filiale)

        materiel_sans_affectation = gm_qs.annotate(
            has_active=Exists(
                active_affectations.filter(code_materiel=OuterRef("code_materiel"))
            )
        ).filter(has_active=False)

        count = materiel_sans_affectation.count()
        if count > 0:
            alerts.append(
                {
                    "type": "warning",
                    "title": "Matériel sans affectation active",
                    "message": f"{count} matériel actif n'a pas d'affectation en cours.",
                    "count": count,
                    "href": "/gestion/grand-materiel",
                }
            )

        three_months_ago = date.today() - timedelta(days=90)
        recent_pointage_materials = pointage_qs.filter(
            mmaa__gte=three_months_ago
        ).values_list("affectation_id__code_materiel", flat=True)

        count = gm_qs.exclude(code_materiel__in=recent_pointage_materials).count()
        if count > 0:
            alerts.append(
                {
                    "type": "warning",
                    "title": "Pointage récent manquant",
                    "message": f"{count} matériel n'a pas de pointage dans les 3 derniers mois.",
                    "count": count,
                    "href": "/gestion/pointages",
                }
            )

        affectations_sans_situation = aff_qs.annotate(
            has_situation=Exists(
                Situation_Materiel.objects.filter(
                    affectation_id=OuterRef("pk"),
                    est_bloque=False,
                )
            )
        ).filter(has_situation=False)

        count = affectations_sans_situation.count()
        if count > 0:
            alerts.append(
                {
                    "type": "info",
                    "title": "Affectations sans situation",
                    "message": f"{count} affectation(s) n'ont pas de situation enregistrée.",
                    "count": count,
                    "href": "/gestion/situations",
                }
            )

        count = pointage_qs.filter(taux_location__isnull=True).count()
        if count > 0:
            alerts.append(
                {
                    "type": "danger",
                    "title": "Pointages sans taux de location",
                    "message": f"{count} pointage(s) ont un taux de location non défini.",
                    "count": count,
                    "href": "/gestion/pointages",
                }
            )

        count = Regularisation_GM.objects.filter(
            est_bloque=False,
            montant_regularisation__lt=0,
        ).count()
        if count > 0:
            alerts.append(
                {
                    "type": "danger",
                    "title": "Regularisations négatives",
                    "message": f"{count} regularisation(s) ont un montant negatif.",
                    "count": count,
                    "href": "/gestion/regularisations-gm",
                }
            )

        return alerts

    @staticmethod
    def _get_recent_activity(limit=20):
        entries = (
            Journal.objects.select_related("user")
            .order_by("-date_action")[:limit]
            .values(
                "id",
                "date_action",
                "action",
                "module",
                "description",
                "objet_type",
                "objet_id",
                "user__username",
            )
        )

        return [
            {
                "id": entry["id"],
                "date_action": entry["date_action"].isoformat() if entry["date_action"] else None,
                "action": entry["action"],
                "module": entry["module"],
                "description": entry["description"],
                "objet_type": entry["objet_type"],
                "objet_id": entry["objet_id"],
                "user": (
                    {"username": entry["user__username"]}
                    if entry["user__username"]
                    else None
                ),
            }
            for entry in entries
        ]
