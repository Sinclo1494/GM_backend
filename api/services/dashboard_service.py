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
    TruncWeek,
    TruncQuarter,
    Coalesce,
    ExtractYear,
    Now,
)

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
        niveau="engin",
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
        global_kpis = DashboardService._get_global_kpis(
            code_filiale, date_debut, date_fin, code_famille
        )
        availability_breakdown = DashboardService._get_availability_breakdown(
            code_filiale, date_debut, date_fin, code_famille, niveau
        )
        panne_breakdown = DashboardService._get_panne_breakdown(
            code_filiale, date_debut, date_fin, code_famille, niveau
        )
        mtbf_evolution = DashboardService._get_mtbf_evolution(
            code_filiale, date_debut, date_fin
        )
        mtbf_breakdown = DashboardService._get_mtbf_breakdown(
            code_filiale, date_debut, date_fin, code_famille, niveau
        )
        mttr_evolution = DashboardService._get_mttr_evolution(
            code_filiale, date_debut, date_fin
        )
        mttr_breakdown = DashboardService._get_mttr_breakdown(
            code_filiale, date_debut, date_fin, code_famille, niveau
        )
        taux_utilisation_evolution = DashboardService._get_taux_utilisation_evolution(
            code_filiale, date_debut, date_fin
        )
        taux_utilisation_breakdown = DashboardService._get_taux_utilisation_breakdown(
            code_filiale, date_debut, date_fin, code_famille, niveau
        )
        taux_chomage_evolution = DashboardService._get_taux_chomage_evolution(
            code_filiale, date_debut, date_fin
        )
        taux_chomage_breakdown = DashboardService._get_taux_chomage_breakdown(
            code_filiale, date_debut, date_fin, code_famille, niveau
        )
        taux_affectation_evolution = DashboardService._get_taux_affectation_evolution(
            code_filiale, date_debut, date_fin
        )
        taux_affectation_breakdown = DashboardService._get_taux_affectation_breakdown(
            code_filiale, date_debut, date_fin, code_famille, niveau
        )
        ca_location_interne_evolution = DashboardService._get_ca_location_interne_evolution(
            code_filiale, date_debut, date_fin, code_famille
        )
        ca_location_interne_breakdown = DashboardService._get_ca_location_interne_breakdown(
            code_filiale, date_debut, date_fin, code_famille, niveau
        )
        cout_panne_evolution = DashboardService._get_cout_panne_evolution(
            code_filiale, date_debut, date_fin, code_famille
        )
        cout_panne_breakdown = DashboardService._get_cout_panne_breakdown(
            code_filiale, date_debut, date_fin, code_famille, niveau
        )
        rendement_evolution = DashboardService._get_rendement_evolution(
            code_filiale, date_debut, date_fin, code_famille
        )
        rendement_breakdown = DashboardService._get_rendement_breakdown(
            code_filiale, date_debut, date_fin, code_famille, niveau
        )
        rentabilite_evolution = DashboardService._get_rentabilite_evolution(
            code_filiale, date_debut, date_fin, code_famille
        )
        rentabilite_ranking = DashboardService._get_rentabilite_classement(
            code_filiale, date_debut, date_fin, code_famille
        )
        material_details = DashboardService._get_material_details(
            code_filiale, date_debut, date_fin, code_famille, page=1, page_size=50
        )

        result = {
            "overview": overview,
            "situationDistribution": situation_distribution,
            "pointageEvolution": pointage_evolution,
            "disponibiliteEvolution": pointage_evolution,
            "filialeStats": filiale_stats,
            "alerts": alerts,
            "recentActivity": recent_activity,
            "familleDistribution": famille_distribution,
            "trends": trends,
            "globalKpis": global_kpis,
            "financialKpis": financial_kpis,
            "maintenanceKpis": maintenance_kpis,
            "availabilityBreakdown": availability_breakdown,
            "panneBreakdown": panne_breakdown,
            "mtbfEvolution": mtbf_evolution,
            "mtbfBreakdown": mtbf_breakdown,
            "mttrEvolution": mttr_evolution,
            "mttrBreakdown": mttr_breakdown,
            "tauxPanneEvolution": pointage_evolution,
            "tauxUtilisationEvolution": taux_utilisation_evolution,
            "tauxUtilisationBreakdown": taux_utilisation_breakdown,
            "tauxChomageEvolution": taux_chomage_evolution,
            "tauxChomageBreakdown": taux_chomage_breakdown,
            "tauxAffectationEvolution": taux_affectation_evolution,
            "tauxAffectationBreakdown": taux_affectation_breakdown,
            "caLocationInterneEvolution": ca_location_interne_evolution,
            "caLocationInterneBreakdown": ca_location_interne_breakdown,
            "coutPanneEvolution": cout_panne_evolution,
            "coutPanneBreakdown": cout_panne_breakdown,
            "rendementEvolution": rendement_evolution,
            "rendementBreakdown": rendement_breakdown,
            "rentabiliteEvolution": rentabilite_evolution,
            "rentabiliteRanking": rentabilite_ranking,
            "materialDetails": material_details,
            "filters": {
                "code_filiale": code_filiale,
                "date_debut": date_debut,
                "date_fin": date_fin,
                "code_famille": code_famille,
                "periode": periode,
                "mode": mode,
                "niveau": niveau,
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
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            )
            .order_by("month")
        )

        return [
            {
                "mmaa": row["month"].strftime("%Y-%m-%d") if row["month"] else None,
                "heures_service": float(row["heures_service"]),
                "heures_chomage": float(row["heures_chomage"]),
                "heures_panne": float(row["heures_panne"]),
                "potentiel": float(row["potentiel"]),
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
        fact_chomage = float(pointage_agg["total_montant_chomage"])
        fact_panne = float(pointage_agg["total_montant_panne"])

        potentiel_qs = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
            affectation_id__prenable=True,
        )
        if code_filiale:
            potentiel_qs = potentiel_qs.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )
        if code_famille:
            potentiel_qs = potentiel_qs.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        potentiel_agg = potentiel_qs.aggregate(
            total_potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ca_potentiel=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("potentiel") * F("taux_location"),
                        output_field=DecimalField(max_digits=30, decimal_places=7),
                    )
                ),
                Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
            ),
        )

        ca_potentiel = float(potentiel_agg["ca_potentiel"])

        manque_a_gagner = ca_potentiel - total_facture if ca_potentiel > total_facture else 0

        ecart_cible_mag = 0
        if ca_potentiel > 0:
            ecart_cible_mag = ((total_facture - ca_potentiel) / ca_potentiel * 100)

        return {
            "totalFacture": total_facture,
            "factService": fact_service,
            "factChomage": fact_chomage,
            "factPanne": fact_panne,
            "manqueAGagner": manque_a_gagner,
            "caPotentiel": ca_potentiel,
            "totalRegularisation": float(reg_agg["total_regularisation"]),
            "marge": fact_service - float(reg_agg["total_regularisation"]),
            "ecartCibleMag": round(ecart_cible_mag, 1),
        }

    @staticmethod
    def _get_global_kpis(code_filiale, date_debut, date_fin, code_famille=None):
        gm_qs = Grand_Materiel.objects.all()
        if code_filiale:
            gm_qs = gm_qs.filter(code_filiale_g=code_filiale)

        situations = Situation_Materiel.objects.filter(
            date_situation__date__lte=date_fin,
            est_bloque=False,
        )
        if code_filiale:
            situations = situations.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )
        if code_famille:
            situations = situations.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
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

        latest = Situation_Materiel.objects.filter(id__in=latest_ids)
        latest = latest.select_related(
            "type_situation_id",
            "type_situation_id__code_type_affectation",
        )

        en_service = 0
        en_chomage = 0
        en_panne = 0
        immobilise_base = 0
        alrem = 0

        for s in latest:
            type_affectation = s.type_situation_id.code_type_affectation.code_type_affectation if s.type_situation_id and s.type_situation_id.code_type_affectation else None
            type_situation = s.type_situation_id.code_type_situation if s.type_situation_id else None

            if type_affectation == "01":
                if type_situation == "01":
                    en_service += 1
                elif type_situation == "02":
                    en_chomage += 1
                elif type_situation == "03":
                    en_panne += 1
            elif type_affectation == "04":
                immobilise_base += 1
            elif type_affectation == "02" and type_situation == "06":
                alrem += 1

        parc_total = gm_qs.count()

        age_total = 0
        age_divider = 0
        age_agg = gm_qs.filter(date_acquisition__isnull=False).aggregate(
            avg_age=Avg(
                ExpressionWrapper(
                    ExtractYear(Now()) - ExtractYear(F("date_acquisition")),
                    output_field=IntegerField(),
                )
            ),
            count=Count("id"),
        )
        age_moyen = int(age_agg["avg_age"] or 0)

        return {
            "parc_total": parc_total,
            "en_service": en_service,
            "en_chomage": en_chomage,
            "en_panne": en_panne,
            "immobilise_base": immobilise_base,
            "alrem": alrem,
            "age_moyen": age_moyen,
        }

    @staticmethod
    def _get_maintenance_kpis(code_filiale, date_debut, date_fin, code_famille=None):
        situations = Situation_Materiel.objects.filter(
            date_situation__date__lte=date_fin,
            est_bloque=False,
        )
        if code_filiale:
            situations = situations.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )
        if code_famille:
            situations = situations.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
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

        latest = Situation_Materiel.objects.filter(id__in=latest_ids)
        latest = latest.select_related(
            "type_situation_id",
            "type_situation_id__code_type_affectation",
        )

        total_materiel = Grand_Materiel.objects.filter(est_bloque=False)
        if code_filiale:
            total_materiel = total_materiel.filter(code_filiale_g=code_filiale)
        if code_famille:
            total_materiel = total_materiel.filter(
                code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )
        total_materiel = total_materiel.count()

        en_panne = 0
        en_reparation = 0

        for s in latest:
            type_affectation = s.type_situation_id.code_type_affectation.code_type_affectation if s.type_situation_id and s.type_situation_id.code_type_affectation else None
            type_situation = s.type_situation_id.code_type_situation if s.type_situation_id else None
            if type_affectation == "01" and type_situation == "03":
                en_panne += 1
            elif type_affectation == "04" and type_situation == "04":
                en_reparation += 1

        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
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
            total_heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            total_heures_chomage=Coalesce(Sum("heures_chomage"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            total_heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            total_potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
        )

        heures_service = float(pointage_agg["total_heures_service"])
        heures_chomage = float(pointage_agg["total_heures_chomage"])
        heures_panne = float(pointage_agg["total_heures_panne"])
        potentiel_total = float(pointage_agg["total_potentiel"])

        tip = (en_panne / total_materiel * 100) if total_materiel else 0

        if potentiel_total > 0:
            taux_service = (heures_service / potentiel_total * 100)
            taux_panne = (heures_panne / potentiel_total * 100)
            disponibilite = ((potentiel_total - heures_panne) / potentiel_total * 100)
            tamd = ((potentiel_total - heures_panne) / potentiel_total * 100)
        else:
            taux_service = 0
            taux_panne = 0
            disponibilite = 0
            tamd = 0

        tam = disponibilite

        return {
            "tamd": round(tamd, 1),
            "tam": round(tam, 1),
            "tip": round(tip, 1),
            "note": "",
            "en_panne": en_panne,
            "en_reparation": en_reparation,
            "taux_service": round(taux_service, 1),
            "taux_panne": round(taux_panne, 1),
            "disponibilite": round(disponibilite, 1),
            "potentiel_total": round(potentiel_total, 1),
            "heures_service": heures_service,
            "heures_chomage": heures_chomage,
            "heures_panne": heures_panne,
        }

    @staticmethod
    def _get_availability_breakdown(code_filiale, date_debut, date_fin, code_famille=None, niveau="engin"):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        if code_famille:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        if niveau == "engin":
            qs = pointages.values(
                "affectation_id__code_materiel",
                "affectation_id__code_materiel__designation",
            ).annotate(
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel")
            return [
                {
                    "code": row["affectation_id__code_materiel"],
                    "libelle": row["affectation_id__code_materiel__designation"],
                    "potentiel": float(row["potentiel"]),
                    "heures_panne": float(row["heures_panne"]),
                    "disponibilite": (float(row["potentiel"]) - float(row["heures_panne"])) / float(row["potentiel"]) * 100 if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "famille":
            qs = pointages.values(
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille",
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille",
            ).annotate(
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille")
            return [
                {
                    "code": row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille"],
                    "libelle": row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille"],
                    "potentiel": float(row["potentiel"]),
                    "heures_panne": float(row["heures_panne"]),
                    "disponibilite": (float(row["potentiel"]) - float(row["heures_panne"])) / float(row["potentiel"]) * 100 if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "chantier":
            qs = pointages.values(
                "affectation_id__code_site",
                "affectation_id__code_site__libelle_site",
            ).annotate(
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_site")
            return [
                {
                    "code": row["affectation_id__code_site"],
                    "libelle": row["affectation_id__code_site__libelle_site"],
                    "potentiel": float(row["potentiel"]),
                    "heures_panne": float(row["heures_panne"]),
                    "disponibilite": (float(row["potentiel"]) - float(row["heures_panne"])) / float(row["potentiel"]) * 100 if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "groupe":
            qs = pointages.values(
                "affectation_id__code_materiel__code_filiale_g",
                "affectation_id__code_materiel__code_filiale_g__libelle_filiale",
            ).annotate(
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel__code_filiale_g")
            return [
                {
                    "code": row["affectation_id__code_materiel__code_filiale_g"],
                    "libelle": row["affectation_id__code_materiel__code_filiale_g__libelle_filiale"],
                    "potentiel": float(row["potentiel"]),
                    "heures_panne": float(row["heures_panne"]),
                    "disponibilite": (float(row["potentiel"]) - float(row["heures_panne"])) / float(row["potentiel"]) * 100 if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        return []

    @staticmethod
    def _get_panne_breakdown(code_filiale, date_debut, date_fin, code_famille=None, niveau="engin"):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        if code_famille:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        if niveau == "engin":
            qs = pointages.values(
                "affectation_id__code_materiel",
                "affectation_id__code_materiel__designation",
            ).annotate(
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel")
            return [
                {
                    "code": row["affectation_id__code_materiel"],
                    "libelle": row["affectation_id__code_materiel__designation"],
                    "potentiel": float(row["potentiel"]),
                    "heures_panne": float(row["heures_panne"]),
                    "taux_panne": (float(row["heures_panne"]) / float(row["potentiel"]) * 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "famille":
            qs = pointages.values(
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille",
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille",
            ).annotate(
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille")
            return [
                {
                    "code": row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille"],
                    "libelle": row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille"],
                    "potentiel": float(row["potentiel"]),
                    "heures_panne": float(row["heures_panne"]),
                    "taux_panne": (float(row["heures_panne"]) / float(row["potentiel"]) * 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "chantier":
            qs = pointages.values(
                "affectation_id__code_site",
                "affectation_id__code_site__libelle_site",
            ).annotate(
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_site")
            return [
                {
                    "code": row["affectation_id__code_site"],
                    "libelle": row["affectation_id__code_site__libelle_site"],
                    "potentiel": float(row["potentiel"]),
                    "heures_panne": float(row["heures_panne"]),
                    "taux_panne": (float(row["heures_panne"]) / float(row["potentiel"]) * 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "groupe":
            qs = pointages.values(
                "affectation_id__code_materiel__code_filiale_g",
                "affectation_id__code_materiel__code_filiale_g__libelle_filiale",
            ).annotate(
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel__code_filiale_g")
            return [
                {
                    "code": row["affectation_id__code_materiel__code_filiale_g"],
                    "libelle": row["affectation_id__code_materiel__code_filiale_g__libelle_filiale"],
                    "potentiel": float(row["potentiel"]),
                    "heures_panne": float(row["heures_panne"]),
                    "taux_panne": (float(row["heures_panne"]) / float(row["potentiel"]) * 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        return []

    @staticmethod
    def _get_mtbf_evolution(code_filiale, date_debut, date_fin):
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
                nombre_pannes=Coalesce(Count("id", filter=Q(heures_panne__gt=0)), Value(0, output_field=IntegerField())),
            )
            .order_by("month")
        )

        return [
            {
                "mmaa": row["month"].strftime("%Y-%m-%d") if row["month"] else None,
                "heures_service": float(row["heures_service"]),
                "nombre_pannes": row["nombre_pannes"],
            }
            for row in evolution
        ]

    @staticmethod
    def _get_mtbf_breakdown(code_filiale, date_debut, date_fin, code_famille=None, niveau="engin"):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        if code_famille:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        if niveau == "engin":
            qs = pointages.values(
                "affectation_id__code_materiel",
                "affectation_id__code_materiel__designation",
            ).annotate(
                heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                nombre_pannes=Coalesce(Count("id", filter=Q(heures_panne__gt=0)), Value(0, output_field=IntegerField())),
            ).order_by("affectation_id__code_materiel")
            return [
                {
                    "code": row["affectation_id__code_materiel"],
                    "libelle": row["affectation_id__code_materiel__designation"],
                    "heures_service": float(row["heures_service"]),
                    "nombre_pannes": row["nombre_pannes"],
                }
                for row in qs
            ]
        elif niveau == "famille":
            qs = pointages.values(
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille",
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille",
            ).annotate(
                heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                nombre_pannes=Coalesce(Count("id", filter=Q(heures_panne__gt=0)), Value(0, output_field=IntegerField())),
            ).order_by("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille")
            return [
                {
                    "code": row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille"],
                    "libelle": row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille"],
                    "heures_service": float(row["heures_service"]),
                    "nombre_pannes": row["nombre_pannes"],
                }
                for row in qs
            ]
        elif niveau == "chantier":
            qs = pointages.values(
                "affectation_id__code_site",
                "affectation_id__code_site__libelle_site",
            ).annotate(
                heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                nombre_pannes=Coalesce(Count("id", filter=Q(heures_panne__gt=0)), Value(0, output_field=IntegerField())),
            ).order_by("affectation_id__code_site")
            return [
                {
                    "code": row["affectation_id__code_site"],
                    "libelle": row["affectation_id__code_site__libelle_site"],
                    "heures_service": float(row["heures_service"]),
                    "nombre_pannes": row["nombre_pannes"],
                }
                for row in qs
            ]
        elif niveau == "groupe":
            qs = pointages.values(
                "affectation_id__code_materiel__code_filiale_g",
                "affectation_id__code_materiel__code_filiale_g__libelle_filiale",
            ).annotate(
                heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                nombre_pannes=Coalesce(Count("id", filter=Q(heures_panne__gt=0)), Value(0, output_field=IntegerField())),
            ).order_by("affectation_id__code_materiel__code_filiale_g")
            return [
                {
                    "code": row["affectation_id__code_materiel__code_filiale_g"],
                    "libelle": row["affectation_id__code_materiel__code_filiale_g__libelle_filiale"],
                    "heures_service": float(row["heures_service"]),
                    "nombre_pannes": row["nombre_pannes"],
                }
                for row in qs
            ]
        return []

    @staticmethod
    def _get_mttr_evolution(code_filiale, date_debut, date_fin):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        sum_qs = (
            pointages.annotate(month=TruncMonth("mmaa"))
            .values("month")
            .annotate(
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            )
            .order_by("month")
        )

        count_qs = (
            pointages.annotate(month=TruncMonth("mmaa"))
            .values("month")
            .annotate(
                interventions_correctives=Coalesce(Count("id", filter=Q(heures_panne__gt=0)), Value(0, output_field=IntegerField())),
            )
            .order_by("month")
        )

        sum_map = {row["month"]: row for row in sum_qs}
        count_map = {row["month"]: row for row in count_qs}

        all_months = sorted(
            set(sum_map.keys()) | set(count_map.keys()),
            key=lambda m: m or "",
        )

        return [
            {
                "mmaa": month.strftime("%Y-%m-%d") if month else None,
                "heures_panne": float(sum_map.get(month, {}).get("heures_panne", 0)),
                "interventions_correctives": count_map.get(month, {}).get("interventions_correctives", 0),
            }
            for month in all_months
        ]

    @staticmethod
    def _get_mttr_breakdown(code_filiale, date_debut, date_fin, code_famille=None, niveau="engin"):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        if code_famille:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        if niveau == "engin":
            sum_qs = pointages.values(
                "affectation_id__code_materiel",
                "affectation_id__code_materiel__designation",
            ).annotate(
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel")

            count_qs = pointages.values(
                "affectation_id__code_materiel",
                "affectation_id__code_materiel__designation",
            ).annotate(
                interventions_correctives=Coalesce(Count("id", filter=Q(heures_panne__gt=0)), Value(0, output_field=IntegerField())),
            ).order_by("affectation_id__code_materiel")

            sum_map = {row["affectation_id__code_materiel"]: row for row in sum_qs}
            count_map = {row["affectation_id__code_materiel"]: row for row in count_qs}
            all_keys = sorted(set(sum_map.keys()) | set(count_map.keys()))

            return [
                {
                    "code": key,
                    "libelle": sum_map.get(key, {}).get("affectation_id__code_materiel__designation") or count_map.get(key, {}).get("affectation_id__code_materiel__designation", key),
                    "heures_panne": float(sum_map.get(key, {}).get("heures_panne", 0)),
                    "interventions_correctives": count_map.get(key, {}).get("interventions_correctives", 0),
                    "mttr": (float(sum_map.get(key, {}).get("heures_panne", 0)) / count_map.get(key, {}).get("interventions_correctives", 1)) if count_map.get(key, {}).get("interventions_correctives", 0) > 0 else None,
                }
                for key in all_keys
            ]
        elif niveau == "famille":
            sum_qs = pointages.values(
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille",
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille",
            ).annotate(
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille")

            count_qs = pointages.values(
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille",
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille",
            ).annotate(
                interventions_correctives=Coalesce(Count("id", filter=Q(heures_panne__gt=0)), Value(0, output_field=IntegerField())),
            ).order_by("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille")

            sum_map = {row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille"]: row for row in sum_qs}
            count_map = {row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille"]: row for row in count_qs}
            all_keys = sorted(set(sum_map.keys()) | set(count_map.keys()))

            return [
                {
                    "code": key,
                    "libelle": sum_map.get(key, {}).get("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille") or count_map.get(key, {}).get("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille", key),
                    "heures_panne": float(sum_map.get(key, {}).get("heures_panne", 0)),
                    "interventions_correctives": count_map.get(key, {}).get("interventions_correctives", 0),
                    "mttr": (float(sum_map.get(key, {}).get("heures_panne", 0)) / count_map.get(key, {}).get("interventions_correctives", 1)) if count_map.get(key, {}).get("interventions_correctives", 0) > 0 else None,
                }
                for key in all_keys
            ]
        elif niveau == "chantier":
            sum_qs = pointages.values(
                "affectation_id__code_site",
                "affectation_id__code_site__libelle_site",
            ).annotate(
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_site")

            count_qs = pointages.values(
                "affectation_id__code_site",
                "affectation_id__code_site__libelle_site",
            ).annotate(
                interventions_correctives=Coalesce(Count("id", filter=Q(heures_panne__gt=0)), Value(0, output_field=IntegerField())),
            ).order_by("affectation_id__code_site")

            sum_map = {row["affectation_id__code_site"]: row for row in sum_qs}
            count_map = {row["affectation_id__code_site"]: row for row in count_qs}
            all_keys = sorted(set(sum_map.keys()) | set(count_map.keys()))

            return [
                {
                    "code": key,
                    "libelle": sum_map.get(key, {}).get("affectation_id__code_site__libelle_site") or count_map.get(key, {}).get("affectation_id__code_site__libelle_site", key),
                    "heures_panne": float(sum_map.get(key, {}).get("heures_panne", 0)),
                    "interventions_correctives": count_map.get(key, {}).get("interventions_correctives", 0),
                    "mttr": (float(sum_map.get(key, {}).get("heures_panne", 0)) / count_map.get(key, {}).get("interventions_correctives", 1)) if count_map.get(key, {}).get("interventions_correctives", 0) > 0 else None,
                }
                for key in all_keys
            ]
        elif niveau == "groupe":
            sum_qs = pointages.values(
                "affectation_id__code_materiel__code_filiale_g",
                "affectation_id__code_materiel__code_filiale_g__libelle_filiale",
            ).annotate(
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel__code_filiale_g")

            count_qs = pointages.values(
                "affectation_id__code_materiel__code_filiale_g",
                "affectation_id__code_materiel__code_filiale_g__libelle_filiale",
            ).annotate(
                interventions_correctives=Coalesce(Count("id", filter=Q(heures_panne__gt=0)), Value(0, output_field=IntegerField())),
            ).order_by("affectation_id__code_materiel__code_filiale_g")

            sum_map = {row["affectation_id__code_materiel__code_filiale_g"]: row for row in sum_qs}
            count_map = {row["affectation_id__code_materiel__code_filiale_g"]: row for row in count_qs}
            all_keys = sorted(set(sum_map.keys()) | set(count_map.keys()))

            return [
                {
                    "code": key,
                    "libelle": sum_map.get(key, {}).get("affectation_id__code_materiel__code_filiale_g__libelle_filiale") or count_map.get(key, {}).get("affectation_id__code_materiel__code_filiale_g__libelle_filiale", key),
                    "heures_panne": float(sum_map.get(key, {}).get("heures_panne", 0)),
                    "interventions_correctives": count_map.get(key, {}).get("interventions_correctives", 0),
                    "mttr": (float(sum_map.get(key, {}).get("heures_panne", 0)) / count_map.get(key, {}).get("interventions_correctives", 1)) if count_map.get(key, {}).get("interventions_correctives", 0) > 0 else None,
                }
                for key in all_keys
            ]
        return []

    @staticmethod
    def _get_taux_utilisation_evolution(code_filiale, date_debut, date_fin):
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
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            )
            .order_by("month")
        )

        return [
            {
                "mmaa": row["month"].strftime("%Y-%m-%d") if row["month"] else None,
                "heures_service": float(row["heures_service"]),
                "potentiel": float(row["potentiel"]),
            }
            for row in evolution
        ]

    @staticmethod
    def _get_taux_utilisation_breakdown(code_filiale, date_debut, date_fin, code_famille=None, niveau="engin"):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        if code_famille:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        if niveau == "engin":
            qs = pointages.values(
                "affectation_id__code_materiel",
                "affectation_id__code_materiel__designation",
            ).annotate(
                heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel")
            return [
                {
                    "code": row["affectation_id__code_materiel"],
                    "libelle": row["affectation_id__code_materiel__designation"],
                    "heures_service": float(row["heures_service"]),
                    "potentiel": float(row["potentiel"]),
                    "taux_utilisation": (float(row["heures_service"]) / float(row["potentiel"]) * 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "famille":
            qs = pointages.values(
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille",
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille",
            ).annotate(
                heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille")
            return [
                {
                    "code": row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille"],
                    "libelle": row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille"],
                    "heures_service": float(row["heures_service"]),
                    "potentiel": float(row["potentiel"]),
                    "taux_utilisation": (float(row["heures_service"]) / float(row["potentiel"]) * 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "chantier":
            qs = pointages.values(
                "affectation_id__code_site",
                "affectation_id__code_site__libelle_site",
            ).annotate(
                heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_site")
            return [
                {
                    "code": row["affectation_id__code_site"],
                    "libelle": row["affectation_id__code_site__libelle_site"],
                    "heures_service": float(row["heures_service"]),
                    "potentiel": float(row["potentiel"]),
                    "taux_utilisation": (float(row["heures_service"]) / float(row["potentiel"]) * 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "groupe":
            qs = pointages.values(
                "affectation_id__code_materiel__code_filiale_g",
                "affectation_id__code_materiel__code_filiale_g__libelle_filiale",
            ).annotate(
                heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel__code_filiale_g")
            return [
                {
                    "code": row["affectation_id__code_materiel__code_filiale_g"],
                    "libelle": row["affectation_id__code_materiel__code_filiale_g__libelle_filiale"],
                    "heures_service": float(row["heures_service"]),
                    "potentiel": float(row["potentiel"]),
                    "taux_utilisation": (float(row["heures_service"]) / float(row["potentiel"]) * 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        return []

    @staticmethod
    def _get_taux_chomage_evolution(code_filiale, date_debut, date_fin):
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
                heures_chomage=Coalesce(Sum("heures_chomage"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            )
            .order_by("month")
        )

        return [
            {
                "mmaa": row["month"].strftime("%Y-%m-%d") if row["month"] else None,
                "heures_chomage": float(row["heures_chomage"]),
                "potentiel": float(row["potentiel"]),
            }
            for row in evolution
        ]

    @staticmethod
    def _get_taux_chomage_breakdown(code_filiale, date_debut, date_fin, code_famille=None, niveau="engin"):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        if code_famille:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        if niveau == "engin":
            qs = pointages.values(
                "affectation_id__code_materiel",
                "affectation_id__code_materiel__designation",
            ).annotate(
                heures_chomage=Coalesce(Sum("heures_chomage"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel")
            return [
                {
                    "code": row["affectation_id__code_materiel"],
                    "libelle": row["affectation_id__code_materiel__designation"],
                    "heures_chomage": float(row["heures_chomage"]),
                    "potentiel": float(row["potentiel"]),
                    "taux_chomage": (float(row["heures_chomage"]) / float(row["potentiel"]) * 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "famille":
            qs = pointages.values(
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille",
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille",
            ).annotate(
                heures_chomage=Coalesce(Sum("heures_chomage"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille")
            return [
                {
                    "code": row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille"],
                    "libelle": row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille"],
                    "heures_chomage": float(row["heures_chomage"]),
                    "potentiel": float(row["potentiel"]),
                    "taux_chomage": (float(row["heures_chomage"]) / float(row["potentiel"]) * 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "chantier":
            qs = pointages.values(
                "affectation_id__code_site",
                "affectation_id__code_site__libelle_site",
            ).annotate(
                heures_chomage=Coalesce(Sum("heures_chomage"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_site")
            return [
                {
                    "code": row["affectation_id__code_site"],
                    "libelle": row["affectation_id__code_site__libelle_site"],
                    "heures_chomage": float(row["heures_chomage"]),
                    "potentiel": float(row["potentiel"]),
                    "taux_chomage": (float(row["heures_chomage"]) / float(row["potentiel"]) * 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "groupe":
            qs = pointages.values(
                "affectation_id__code_materiel__code_filiale_g",
                "affectation_id__code_materiel__code_filiale_g__libelle_filiale",
            ).annotate(
                heures_chomage=Coalesce(Sum("heures_chomage"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel__code_filiale_g")
            return [
                {
                    "code": row["affectation_id__code_materiel__code_filiale_g"],
                    "libelle": row["affectation_id__code_materiel__code_filiale_g__libelle_filiale"],
                    "heures_chomage": float(row["heures_chomage"]),
                    "potentiel": float(row["potentiel"]),
                    "taux_chomage": (float(row["heures_chomage"]) / float(row["potentiel"]) * 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        return []

    @staticmethod
    def _get_taux_affectation_evolution(code_filiale, date_debut, date_fin):
        active_affectations = Affectation_Materiel.objects.filter(
            est_bloque=False,
            date_fin_affectation__isnull=True,
            date_affectation__date__lte=date_fin,
        )
        if code_filiale:
            active_affectations = active_affectations.filter(code_filiale_mere=code_filiale)

        parc_total = Grand_Materiel.objects.filter(est_bloque=False)
        if code_filiale:
            parc_total = parc_total.filter(code_filiale_g=code_filiale)
        parc_total = parc_total.count()

        total_distinct_engins = (
            active_affectations.values("code_materiel")
            .distinct()
            .count()
        )

        evolution = (
            active_affectations.annotate(week=TruncWeek("date_affectation"))
            .values("week")
            .annotate(
                distinct_engins=Count("code_materiel", distinct=True),
            )
            .order_by("week")
        )

        return [
            {
                "week": row["week"].strftime("%Y-%m-%d") if row["week"] else None,
                "distinct_engins": row["distinct_engins"],
                "parc_total": parc_total,
                "total_distinct_engins": total_distinct_engins,
                "taux_affectation": (row["distinct_engins"] / parc_total * 100) if parc_total > 0 else 0,
            }
            for row in evolution
        ]

    @staticmethod
    def _get_taux_affectation_breakdown(code_filiale, date_debut, date_fin, code_famille=None, niveau="engin"):
        active_affectations = Affectation_Materiel.objects.filter(
            est_bloque=False,
            date_fin_affectation__isnull=True,
        )
        if code_filiale:
            active_affectations = active_affectations.filter(code_filiale_mere=code_filiale)

        gm_qs = Grand_Materiel.objects.filter(est_bloque=False)
        if code_filiale:
            gm_qs = gm_qs.filter(code_filiale_g=code_filiale)
        if code_famille:
            gm_qs = gm_qs.filter(code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille)

        if niveau == "engin":
            qs = gm_qs.annotate(
                has_active_affectation=Exists(
                    active_affectations.filter(code_materiel=OuterRef("code_materiel"))
                )
            ).values(
                "code_materiel",
                "designation",
            ).annotate(
                parc_total=Count("id"),
                engins_affectes=Count("id", filter=Q(has_active_affectation=True)),
            ).order_by("code_materiel")
            return [
                {
                    "code": row["code_materiel"],
                    "libelle": row["designation"],
                    "parc_total": row["parc_total"],
                    "engins_affectes": row["engins_affectes"],
                    "taux_affectation": (row["engins_affectes"] / row["parc_total"] * 100) if row["parc_total"] > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "famille":
            qs = gm_qs.annotate(
                has_active_affectation=Exists(
                    active_affectations.filter(code_materiel=OuterRef("code_materiel"))
                )
            ).values(
                "code_sous_famille_materiel__code_famille_materiel__code_famille",
                "code_sous_famille_materiel__code_famille_materiel__libelle_famille",
            ).annotate(
                parc_total=Count("id"),
                engins_affectes=Count("id", filter=Q(has_active_affectation=True)),
            ).order_by("code_sous_famille_materiel__code_famille_materiel__code_famille")
            return [
                {
                    "code": row["code_sous_famille_materiel__code_famille_materiel__code_famille"],
                    "libelle": row["code_sous_famille_materiel__code_famille_materiel__libelle_famille"],
                    "parc_total": row["parc_total"],
                    "engins_affectes": row["engins_affectes"],
                    "taux_affectation": (row["engins_affectes"] / row["parc_total"] * 100) if row["parc_total"] > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "chantier":
            qs = active_affectations.filter(
                code_materiel__in=gm_qs.values_list("code_materiel", flat=True)
            ).values(
                "code_site",
                "code_site__libelle_site",
            ).annotate(
                engins_affectes=Count("code_materiel", distinct=True),
            ).order_by("code_site")
            parc_total = gm_qs.count()
            return [
                {
                    "code": row["code_site"],
                    "libelle": row["code_site__libelle_site"],
                    "parc_total": parc_total,
                    "engins_affectes": row["engins_affectes"],
                    "taux_affectation": (row["engins_affectes"] / parc_total * 100) if parc_total > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "groupe":
            qs = gm_qs.annotate(
                has_active_affectation=Exists(
                    active_affectations.filter(code_materiel=OuterRef("code_materiel"))
                )
            ).values(
                "code_filiale_g",
                "code_filiale_g__libelle_filiale",
            ).annotate(
                parc_total=Count("id"),
                engins_affectes=Count("id", filter=Q(has_active_affectation=True)),
            ).order_by("code_filiale_g")
            return [
                {
                    "code": row["code_filiale_g"],
                    "libelle": row["code_filiale_g__libelle_filiale"],
                    "parc_total": row["parc_total"],
                    "engins_affectes": row["engins_affectes"],
                    "taux_affectation": (row["engins_affectes"] / row["parc_total"] * 100) if row["parc_total"] > 0 else 0,
                }
                for row in qs
            ]
        return []

    @staticmethod
    def _get_ca_location_interne_evolution(code_filiale, date_debut, date_fin, code_famille=None):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
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
                ca_stored=Coalesce(
                    Sum(
                        Case(
                            When(montant_service__isnull=False, then=F("montant_service")),
                            default=Value(0, output_field=DecimalField(max_digits=20, decimal_places=7)),
                            output_field=DecimalField(max_digits=20, decimal_places=7),
                        )
                    ),
                    Value(0, output_field=DecimalField(max_digits=20, decimal_places=7)),
                ),
                ca_calculated=Coalesce(
                    Sum(
                        Case(
                            When(montant_service__isnull=True, taux_location__isnull=False, then=ExpressionWrapper(F("heures_service") * F("taux_location"), output_field=DecimalField(max_digits=30, decimal_places=7))),
                            default=Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
                            output_field=DecimalField(max_digits=30, decimal_places=7),
                        )
                    ),
                    Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
                ),
                total_ca=Coalesce(
                    Sum(
                        Case(
                            When(montant_service__isnull=False, then=F("montant_service")),
                            When(montant_service__isnull=True, taux_location__isnull=False, then=ExpressionWrapper(F("heures_service") * F("taux_location"), output_field=DecimalField(max_digits=30, decimal_places=7))),
                            default=Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
                            output_field=DecimalField(max_digits=30, decimal_places=7),
                        )
                    ),
                    Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
                ),
                records_with_montant=Coalesce(Count("id", filter=Q(montant_service__isnull=False)), Value(0, output_field=IntegerField())),
                records_without_montant=Coalesce(Count("id", filter=Q(montant_service__isnull=True)), Value(0, output_field=IntegerField())),
            )
            .order_by("month")
        )

        return [
            {
                "mmaa": row["month"].strftime("%Y-%m-%d") if row["month"] else None,
                "ca_stored": float(row["ca_stored"]),
                "ca_calculated": float(row["ca_calculated"]),
                "total_ca": float(row["total_ca"]),
                "records_with_montant": row["records_with_montant"],
                "records_without_montant": row["records_without_montant"],
            }
            for row in evolution
        ]

    @staticmethod
    def _get_ca_location_interne_breakdown(code_filiale, date_debut, date_fin, code_famille=None, niveau="engin"):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        if code_famille:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        ca_expr = ExpressionWrapper(
            Case(
                When(montant_service__isnull=False, then=F("montant_service")),
                When(montant_service__isnull=True, taux_location__isnull=False, then=F("heures_service") * F("taux_location")),
                default=Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
                output_field=DecimalField(max_digits=30, decimal_places=7),
            ),
            output_field=DecimalField(max_digits=30, decimal_places=7),
        )

        if niveau == "engin":
            qs = pointages.values(
                "affectation_id__code_materiel",
                "affectation_id__code_materiel__designation",
            ).annotate(
                ca_total=Coalesce(Sum(ca_expr), Value(0, output_field=DecimalField(max_digits=30, decimal_places=7))),
                records_with_montant=Coalesce(Count("id", filter=Q(montant_service__isnull=False)), Value(0, output_field=IntegerField())),
                records_without_montant=Coalesce(Count("id", filter=Q(montant_service__isnull=True)), Value(0, output_field=IntegerField())),
            ).order_by("affectation_id__code_materiel")
            return [
                {
                    "code": row["affectation_id__code_materiel"],
                    "libelle": row["affectation_id__code_materiel__designation"],
                    "ca_total": float(row["ca_total"]),
                    "records_with_montant": row["records_with_montant"],
                    "records_without_montant": row["records_without_montant"],
                }
                for row in qs
            ]
        elif niveau == "famille":
            qs = pointages.values(
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille",
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille",
            ).annotate(
                ca_total=Coalesce(Sum(ca_expr), Value(0, output_field=DecimalField(max_digits=30, decimal_places=7))),
                records_with_montant=Coalesce(Count("id", filter=Q(montant_service__isnull=False)), Value(0, output_field=IntegerField())),
                records_without_montant=Coalesce(Count("id", filter=Q(montant_service__isnull=True)), Value(0, output_field=IntegerField())),
            ).order_by("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille")
            return [
                {
                    "code": row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille"],
                    "libelle": row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille"],
                    "ca_total": float(row["ca_total"]),
                    "records_with_montant": row["records_with_montant"],
                    "records_without_montant": row["records_without_montant"],
                }
                for row in qs
            ]
        elif niveau == "chantier":
            qs = pointages.values(
                "affectation_id__code_site",
                "affectation_id__code_site__libelle_site",
            ).annotate(
                ca_total=Coalesce(Sum(ca_expr), Value(0, output_field=DecimalField(max_digits=30, decimal_places=7))),
                records_with_montant=Coalesce(Count("id", filter=Q(montant_service__isnull=False)), Value(0, output_field=IntegerField())),
                records_without_montant=Coalesce(Count("id", filter=Q(montant_service__isnull=True)), Value(0, output_field=IntegerField())),
            ).order_by("affectation_id__code_site")
            return [
                {
                    "code": row["affectation_id__code_site"],
                    "libelle": row["affectation_id__code_site__libelle_site"],
                    "ca_total": float(row["ca_total"]),
                    "records_with_montant": row["records_with_montant"],
                    "records_without_montant": row["records_without_montant"],
                }
                for row in qs
            ]
        elif niveau == "groupe":
            qs = pointages.values(
                "affectation_id__code_materiel__code_filiale_g",
                "affectation_id__code_materiel__code_filiale_g__libelle_filiale",
            ).annotate(
                ca_total=Coalesce(Sum(ca_expr), Value(0, output_field=DecimalField(max_digits=30, decimal_places=7))),
                records_with_montant=Coalesce(Count("id", filter=Q(montant_service__isnull=False)), Value(0, output_field=IntegerField())),
                records_without_montant=Coalesce(Count("id", filter=Q(montant_service__isnull=True)), Value(0, output_field=IntegerField())),
            ).order_by("affectation_id__code_materiel__code_filiale_g")
            return [
                {
                    "code": row["affectation_id__code_materiel__code_filiale_g"],
                    "libelle": row["affectation_id__code_materiel__code_filiale_g__libelle_filiale"],
                    "ca_total": float(row["ca_total"]),
                    "records_with_montant": row["records_with_montant"],
                    "records_without_montant": row["records_without_montant"],
                }
                for row in qs
            ]
        return []

    @staticmethod
    def _get_cout_panne_evolution(code_filiale, date_debut, date_fin, code_famille=None):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        if code_famille:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        heures_qs = (
            pointages.annotate(month=TruncMonth("mmaa"))
            .values("month")
            .annotate(
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            )
            .order_by("month")
        )

        cout_expr = ExpressionWrapper(
            Case(
                When(taux_location__isnull=False, then=F("heures_panne") * F("taux_location")),
                default=Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
                output_field=DecimalField(max_digits=30, decimal_places=7),
            ),
            output_field=DecimalField(max_digits=30, decimal_places=7),
        )

        cout_qs = (
            pointages.annotate(month=TruncMonth("mmaa"))
            .values("month")
            .annotate(
                cout_panne=Coalesce(Sum(cout_expr), Value(0, output_field=DecimalField(max_digits=30, decimal_places=7))),
                records_with_tarif=Coalesce(Count("id", filter=Q(taux_location__isnull=False)), Value(0, output_field=IntegerField())),
                records_without_tarif=Coalesce(Count("id", filter=Q(taux_location__isnull=True)), Value(0, output_field=IntegerField())),
            )
            .order_by("month")
        )

        heures_map = {row["month"]: row["heures_panne"] for row in heures_qs}
        cout_map = {row["month"]: row for row in cout_qs}
        all_months = sorted(set(heures_map.keys()) | set(cout_map.keys()))

        return [
            {
                "mmaa": month.strftime("%Y-%m-%d") if month else None,
                "heures_panne": float(heures_map.get(month, 0)),
                "cout_panne": float(cout_map.get(month, {}).get("cout_panne", 0)),
                "records_with_tarif": cout_map.get(month, {}).get("records_with_tarif", 0),
                "records_without_tarif": cout_map.get(month, {}).get("records_without_tarif", 0),
            }
            for month in all_months
        ]

    @staticmethod
    def _get_cout_panne_breakdown(code_filiale, date_debut, date_fin, code_famille=None, niveau="engin"):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        if code_famille:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        cout_expr = ExpressionWrapper(
            Case(
                When(taux_location__isnull=False, then=F("heures_panne") * F("taux_location")),
                default=Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
                output_field=DecimalField(max_digits=30, decimal_places=7),
            ),
            output_field=DecimalField(max_digits=30, decimal_places=7),
        )

        def merge_rows(heures_rows, cout_rows, key_fields):
            heures_map = {tuple(row[k] for k in key_fields): row["heures_panne"] for row in heures_rows}
            cout_map = {tuple(row[k] for k in key_fields): row for row in cout_rows}
            all_keys = sorted(set(heures_map.keys()) | set(cout_map.keys()))
            merged = []
            for key in all_keys:
                code = key[0]
                libelle = key[1] if len(key) > 1 else ""
                merged.append({
                    "code": code,
                    "libelle": libelle,
                    "heures_panne": float(heures_map.get(key, 0)),
                    "cout_panne": float(cout_map.get(key, {}).get("cout_panne", 0)),
                    "records_with_tarif": cout_map.get(key, {}).get("records_with_tarif", 0),
                    "records_without_tarif": cout_map.get(key, {}).get("records_without_tarif", 0),
                })
            return merged

        if niveau == "engin":
            heures_qs = pointages.values(
                "affectation_id__code_materiel",
                "affectation_id__code_materiel__designation",
            ).annotate(
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel")

            cout_qs = pointages.values(
                "affectation_id__code_materiel",
                "affectation_id__code_materiel__designation",
            ).annotate(
                cout_panne=Coalesce(Sum(cout_expr), Value(0, output_field=DecimalField(max_digits=30, decimal_places=7))),
                records_with_tarif=Coalesce(Count("id", filter=Q(taux_location__isnull=False)), Value(0, output_field=IntegerField())),
                records_without_tarif=Coalesce(Count("id", filter=Q(taux_location__isnull=True)), Value(0, output_field=IntegerField())),
            ).order_by("-cout_panne")

            return merge_rows(heures_qs, cout_qs, ["affectation_id__code_materiel", "affectation_id__code_materiel__designation"])

        elif niveau == "famille":
            heures_qs = pointages.values(
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille",
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille",
            ).annotate(
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille")

            cout_qs = pointages.values(
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille",
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille",
            ).annotate(
                cout_panne=Coalesce(Sum(cout_expr), Value(0, output_field=DecimalField(max_digits=30, decimal_places=7))),
                records_with_tarif=Coalesce(Count("id", filter=Q(taux_location__isnull=False)), Value(0, output_field=IntegerField())),
                records_without_tarif=Coalesce(Count("id", filter=Q(taux_location__isnull=True)), Value(0, output_field=IntegerField())),
            ).order_by("-cout_panne")

            return merge_rows(heures_qs, cout_qs, ["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille", "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille"])

        elif niveau == "chantier":
            heures_qs = pointages.values(
                "affectation_id__code_site",
                "affectation_id__code_site__libelle_site",
            ).annotate(
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_site")

            cout_qs = pointages.values(
                "affectation_id__code_site",
                "affectation_id__code_site__libelle_site",
            ).annotate(
                cout_panne=Coalesce(Sum(cout_expr), Value(0, output_field=DecimalField(max_digits=30, decimal_places=7))),
                records_with_tarif=Coalesce(Count("id", filter=Q(taux_location__isnull=False)), Value(0, output_field=IntegerField())),
                records_without_tarif=Coalesce(Count("id", filter=Q(taux_location__isnull=True)), Value(0, output_field=IntegerField())),
            ).order_by("-cout_panne")

            return merge_rows(heures_qs, cout_qs, ["affectation_id__code_site", "affectation_id__code_site__libelle_site"])

        elif niveau == "groupe":
            heures_qs = pointages.values(
                "affectation_id__code_materiel__code_filiale_g",
                "affectation_id__code_materiel__code_filiale_g__libelle_filiale",
            ).annotate(
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel__code_filiale_g")

            cout_qs = pointages.values(
                "affectation_id__code_materiel__code_filiale_g",
                "affectation_id__code_materiel__code_filiale_g__libelle_filiale",
            ).annotate(
                cout_panne=Coalesce(Sum(cout_expr), Value(0, output_field=DecimalField(max_digits=30, decimal_places=7))),
                records_with_tarif=Coalesce(Count("id", filter=Q(taux_location__isnull=False)), Value(0, output_field=IntegerField())),
                records_without_tarif=Coalesce(Count("id", filter=Q(taux_location__isnull=True)), Value(0, output_field=IntegerField())),
            ).order_by("-cout_panne")

            return merge_rows(heures_qs, cout_qs, ["affectation_id__code_materiel__code_filiale_g", "affectation_id__code_materiel__code_filiale_g__libelle_filiale"])
        return []

    @staticmethod
    def _get_rendement_evolution(code_filiale, date_debut, date_fin, code_famille=None):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
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
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            )
            .order_by("month")
        )

        result = []
        for row in evolution:
            potentiel = float(row["potentiel"])
            heures_service = float(row["heures_service"])
            heures_panne = float(row["heures_panne"])
            disponibilite = ((potentiel - heures_panne) / potentiel * 100) if potentiel > 0 else 0
            taux_utilisation = (heures_service / potentiel * 100) if potentiel > 0 else 0
            rendement = (disponibilite * taux_utilisation / 100) if potentiel > 0 else 0
            result.append({
                "mmaa": row["month"].strftime("%Y-%m-%d") if row["month"] else None,
                "heures_service": heures_service,
                "heures_panne": heures_panne,
                "potentiel": potentiel,
                "disponibilite": round(disponibilite, 1),
                "taux_utilisation": round(taux_utilisation, 1),
                "rendement": round(rendement, 1),
            })
        return result

    @staticmethod
    def _get_rendement_breakdown(code_filiale, date_debut, date_fin, code_famille=None, niveau="engin"):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        if code_famille:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        if niveau == "engin":
            qs = pointages.values(
                "affectation_id__code_materiel",
                "affectation_id__code_materiel__designation",
            ).annotate(
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel")
            return [
                {
                    "code": row["affectation_id__code_materiel"],
                    "libelle": row["affectation_id__code_materiel__designation"],
                    "potentiel": float(row["potentiel"]),
                    "heures_service": float(row["heures_service"]),
                    "heures_panne": float(row["heures_panne"]),
                    "disponibilite": (float(row["potentiel"]) - float(row["heures_panne"])) / float(row["potentiel"]) * 100 if float(row["potentiel"]) > 0 else 0,
                    "taux_utilisation": float(row["heures_service"]) / float(row["potentiel"]) * 100 if float(row["potentiel"]) > 0 else 0,
                    "rendement": ((float(row["potentiel"]) - float(row["heures_panne"])) / float(row["potentiel"]) * 100 * (float(row["heures_service"]) / float(row["potentiel"]) * 100) / 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "famille":
            qs = pointages.values(
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille",
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille",
            ).annotate(
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille")
            return [
                {
                    "code": row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille"],
                    "libelle": row["affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille"],
                    "potentiel": float(row["potentiel"]),
                    "heures_service": float(row["heures_service"]),
                    "heures_panne": float(row["heures_panne"]),
                    "disponibilite": (float(row["potentiel"]) - float(row["heures_panne"])) / float(row["potentiel"]) * 100 if float(row["potentiel"]) > 0 else 0,
                    "taux_utilisation": float(row["heures_service"]) / float(row["potentiel"]) * 100 if float(row["potentiel"]) > 0 else 0,
                    "rendement": ((float(row["potentiel"]) - float(row["heures_panne"])) / float(row["potentiel"]) * 100 * (float(row["heures_service"]) / float(row["potentiel"]) * 100) / 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "chantier":
            qs = pointages.values(
                "affectation_id__code_site",
                "affectation_id__code_site__libelle_site",
            ).annotate(
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_site")
            return [
                {
                    "code": row["affectation_id__code_site"],
                    "libelle": row["affectation_id__code_site__libelle_site"],
                    "potentiel": float(row["potentiel"]),
                    "heures_service": float(row["heures_service"]),
                    "heures_panne": float(row["heures_panne"]),
                    "disponibilite": (float(row["potentiel"]) - float(row["heures_panne"])) / float(row["potentiel"]) * 100 if float(row["potentiel"]) > 0 else 0,
                    "taux_utilisation": float(row["heures_service"]) / float(row["potentiel"]) * 100 if float(row["potentiel"]) > 0 else 0,
                    "rendement": ((float(row["potentiel"]) - float(row["heures_panne"])) / float(row["potentiel"]) * 100 * (float(row["heures_service"]) / float(row["potentiel"]) * 100) / 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        elif niveau == "groupe":
            qs = pointages.values(
                "affectation_id__code_materiel__code_filiale_g",
                "affectation_id__code_materiel__code_filiale_g__libelle_filiale",
            ).annotate(
                potentiel=Coalesce(Sum("potentiel"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_service=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
                heures_panne=Coalesce(Sum("heures_panne"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
            ).order_by("affectation_id__code_materiel__code_filiale_g")
            return [
                {
                    "code": row["affectation_id__code_materiel__code_filiale_g"],
                    "libelle": row["affectation_id__code_materiel__code_filiale_g__libelle_filiale"],
                    "potentiel": float(row["potentiel"]),
                    "heures_service": float(row["heures_service"]),
                    "heures_panne": float(row["heures_panne"]),
                    "disponibilite": (float(row["potentiel"]) - float(row["heures_panne"])) / float(row["potentiel"]) * 100 if float(row["potentiel"]) > 0 else 0,
                    "taux_utilisation": float(row["heures_service"]) / float(row["potentiel"]) * 100 if float(row["potentiel"]) > 0 else 0,
                    "rendement": ((float(row["potentiel"]) - float(row["heures_panne"])) / float(row["potentiel"]) * 100 * (float(row["heures_service"]) / float(row["potentiel"]) * 100) / 100) if float(row["potentiel"]) > 0 else 0,
                }
                for row in qs
            ]
        return []

    @staticmethod
    def _get_rentabilite_evolution(code_filiale, date_debut, date_fin, code_famille=None):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        if code_famille:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        ca_expr = ExpressionWrapper(
            Case(
                When(montant_service__isnull=False, then=F("montant_service")),
                When(montant_service__isnull=True, taux_location__isnull=False, then=F("heures_service") * F("taux_location")),
                default=Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
                output_field=DecimalField(max_digits=30, decimal_places=7),
            ),
            output_field=DecimalField(max_digits=30, decimal_places=7),
        )

        evolution = (
            pointages.annotate(quarter=TruncQuarter("mmaa"))
            .values("quarter")
            .annotate(
                chiffre_affaires=Coalesce(Sum(ca_expr), Value(0, output_field=DecimalField(max_digits=30, decimal_places=7))),
            )
            .order_by("quarter")
        )

        reg_qs = Regularisation_GM.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )
        if code_filiale:
            reg_qs = reg_qs.filter(code_site__code_filiale=code_filiale)

        reg_evolution = (
            reg_qs.annotate(quarter=TruncQuarter("mmaa"))
            .values("quarter")
            .annotate(
                regularisation=Coalesce(Sum("montant_regularisation"), Value(0, output_field=DecimalField(max_digits=20, decimal_places=4))),
            )
            .order_by("quarter")
        )

        reg_map = {row["quarter"]: float(row["regularisation"]) for row in reg_evolution}

        result = []
        for row in evolution:
            ca = float(row["chiffre_affaires"])
            quarter = row["quarter"]
            reg = reg_map.get(quarter, 0)
            result.append({
                "quarter": quarter.strftime("%Y-%m-%d") if quarter else None,
                "chiffre_affaires": round(ca, 2),
                "regularisation": round(reg, 2),
                "marge": round(ca - reg, 2),
            })
        return result

    @staticmethod
    def _get_rentabilite_classement(code_filiale, date_debut, date_fin, code_famille=None):
        pointages = Pointage.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        ).select_related(
            "affectation_id__code_materiel",
            "affectation_id__code_materiel__code_filiale_g",
            "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel",
            "affectation_id__code_site",
        )

        if code_filiale:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_filiale_g=code_filiale
            )

        if code_famille:
            pointages = pointages.filter(
                affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille=code_famille
            )

        ca_expr = ExpressionWrapper(
            Case(
                When(montant_service__isnull=False, then=F("montant_service")),
                When(montant_service__isnull=True, taux_location__isnull=False, then=F("heures_service") * F("taux_location")),
                default=Value(0, output_field=DecimalField(max_digits=30, decimal_places=7)),
                output_field=DecimalField(max_digits=30, decimal_places=7),
            ),
            output_field=DecimalField(max_digits=30, decimal_places=7),
        )

        engin_ca = {}
        for row in pointages.values(
            "affectation_id__code_materiel",
        ).annotate(
            code_materiel=F("affectation_id__code_materiel"),
            designation=F("affectation_id__code_materiel__designation"),
            code_filiale=F("affectation_id__code_materiel__code_filiale_g__code_filiale"),
            libelle_filiale=F("affectation_id__code_materiel__code_filiale_g__libelle_filiale"),
            code_famille=F("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_famille"),
            libelle_famille=F("affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__libelle_famille"),
            chiffre_affaires=Coalesce(Sum(ca_expr), Value(0, output_field=DecimalField(max_digits=30, decimal_places=7))),
        ).values_list(
            "code_materiel",
            "designation",
            "code_filiale",
            "libelle_filiale",
            "code_famille",
            "libelle_famille",
            "chiffre_affaires",
        ):
            engin_ca[row[0]] = row

        engin_site_heures = {}
        for row in pointages.values(
            "affectation_id__code_materiel",
            "affectation_id__code_site",
            "mmaa",
        ).annotate(
            heures=Coalesce(Sum("heures_service"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=1))),
        ).values_list(
            "affectation_id__code_materiel",
            "affectation_id__code_site",
            "mmaa",
            "heures",
        ):
            engin_site_heures[(row[0], row[1], row[2])] = float(row[3])

        reg_qs = Regularisation_GM.objects.filter(
            mmaa__range=(date_debut, date_fin),
            est_bloque=False,
        )
        if code_filiale:
            reg_qs = reg_qs.filter(code_site__code_filiale=code_filiale)

        reg_map = {}
        for row in reg_qs.values("code_site", "mmaa", "montant_regularisation"):
            reg_map[(row["code_site"], row["mmaa"])] = float(row["montant_regularisation"])

        site_month_total_heures = defaultdict(float)
        for (code_mat, site, month), heures in engin_site_heures.items():
            site_month_total_heures[(site, month)] += heures

        result_map = defaultdict(lambda: {"regularisation": 0.0})
        for (code_mat, site, month), heures in engin_site_heures.items():
            total_heures = site_month_total_heures.get((site, month), 0)
            if total_heures > 0:
                result_map[code_mat]["regularisation"] += reg_map.get((site, month), 0) * (heures / total_heures)

        final_result = []
        for code_mat, ca_data in engin_ca.items():
            designation = ca_data[1]
            code_filiale_val = ca_data[2]
            libelle_filiale = ca_data[3]
            code_famille_val = ca_data[4]
            libelle_famille = ca_data[5]
            chiffre_affaires = float(ca_data[6])
            regularisation = result_map.get(code_mat, {}).get("regularisation", 0)
            marge = chiffre_affaires - regularisation
            final_result.append({
                "code_materiel": code_mat,
                "designation": designation,
                "code_filiale": code_filiale_val,
                "libelle_filiale": libelle_filiale,
                "code_famille": code_famille_val,
                "libelle_famille": libelle_famille,
                "chiffre_affaires": round(chiffre_affaires, 2),
                "regularisation": round(regularisation, 2),
                "marge": round(marge, 2),
            })

        final_result.sort(key=lambda x: x["marge"], reverse=True)
        return final_result

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
