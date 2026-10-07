from datetime import date, datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from api.models import (
    Affectation_Materiel,
    Categorie_GM,
    Division,
    Entreprise,
    Famille_Materiel,
    Filiale,
    Grand_Materiel,
    Pointage,
    Regularisation_GM,
    Site,
    Situation_Materiel,
    Sous_Famille_Materiel,
    Type_Affectation,
    Type_Etat_Materiel,
    Type_Situation,
)
from api.services.dashboard_v2_service import DashboardV2Service


class DashboardV2ServiceTest(TestCase):
    """Tests for the DashboardV2Service aggregation helpers.

    The service runs expensive SQL aggregations against the production
    database. To keep the tests hermetic (no live DB required) every
    DB-dependent subquery is mocked; the assertions focus on the
    service's shaping logic: how breakdown rows are keyed by `niveau`
    and how the maintenance payload merges mtbf/mttr/cout into one dict.
    """

    def _row(self, code, libelle, **extra):
        row = {"code": code, "libelle": libelle}
        row.update(extra)
        return row

    def test_get_disponibilite_breakdown_keyed_by_famille(self):
        # `_ratio_series` returns an (evolution, breakdown) tuple.
        rows = [
            self._row("F1", "Famille 1", potentiel=100, heures_panne=10, disponibilite=90),
            self._row("F2", "Famille 2", potentiel=200, heures_panne=20, disponibilite=95),
        ]

        with (
            mock.patch.object(DashboardV2Service, "_pointage_base", return_value=object()),
            mock.patch.object(
                DashboardV2Service, "_ratio_series", return_value=([], rows)
            ),
        ):
            result = DashboardV2Service.get_disponibilite(
                code_filiale="P",
                date_debut="2026-01-01",
                date_fin="2026-01-31",
                code_famille="",
                niveau="famille",
            )

        self.assertIn("breakdown", result)
        breakdown = result["breakdown"]
        # Breakdown rows must be keyed by famille when niveau='famille'.
        self.assertEqual(len(breakdown), 2)
        self.assertEqual(breakdown[0]["code"], "F1")
        self.assertEqual(breakdown[0]["libelle"], "Famille 1")
        self.assertEqual(breakdown[1]["code"], "F2")
        self.assertEqual(breakdown[1]["libelle"], "Famille 2")

    def test_get_disponibilite_returns_empty_breakdown_when_no_rows(self):
        with (
            mock.patch.object(DashboardV2Service, "_pointage_base", return_value=object()),
            mock.patch.object(
                DashboardV2Service, "_ratio_series", return_value=([], [])
            ),
        ):
            result = DashboardV2Service.get_disponibilite(
                code_filiale="P",
                date_debut="2026-01-01",
                date_fin="2026-01-31",
                code_famille="",
                niveau="famille",
            )

        self.assertEqual(result["breakdown"], [])

    def test_fold_periods_keeps_each_period_separate(self):
        """Each month must keep its own totals, never the last one's.

        `_fold_periods` used to bind only ``period`` in its result
        comprehension and read ``bucket`` from the enclosing loop, so every
        emitted month repeated the *last* bucket: the Disponibilité/Rendement
        evolution curves were flat lines holding a single month's values.
        """
        rows = [
            {
                "mmaa_month": date(2026, 1, 1),
                "heures_service": 100.0,
                "heures_chomage": 10.0,
                "heures_panne": 20.0,
                "potentiel": 200.0,
            },
            {
                "mmaa_month": date(2026, 2, 1),
                "heures_service": 300.0,
                "heures_chomage": 20.0,
                "heures_panne": 30.0,
                "potentiel": 400.0,
            },
            {
                "mmaa_month": date(2026, 3, 1),
                "heures_service": 500.0,
                "heures_chomage": 30.0,
                "heures_panne": 40.0,
                "potentiel": 600.0,
            },
        ]

        folded = DashboardV2Service._fold_periods(rows, "mmaa_month")

        self.assertEqual([row["mmaa"] for row in folded],
                         ["2026-01-01", "2026-02-01", "2026-03-01"])
        self.assertEqual([row["potentiel"] for row in folded], [200.0, 400.0, 600.0])
        self.assertEqual(
            [row["heures_service"] for row in folded], [100.0, 300.0, 500.0]
        )
        # Ratios are recomputed per month from that month's own hours.
        self.assertEqual([row["disponibilite"] for row in folded], [90.0, 92.5, 93.3])
        # The regression itself: no month may be a copy of another.
        self.assertEqual(len({row["potentiel"] for row in folded}), 3)

    def test_fold_periods_sums_entities_within_the_same_period(self):
        """Several entities in one month collapse into a single monthly row."""
        rows = [
            {
                "mmaa_month": date(2026, 1, 1),
                "heures_service": 100.0,
                "heures_chomage": 10.0,
                "heures_panne": 20.0,
                "potentiel": 200.0,
            },
            {
                "mmaa_month": date(2026, 1, 1),
                "heures_service": 50.0,
                "heures_chomage": 5.0,
                "heures_panne": 10.0,
                "potentiel": 100.0,
            },
        ]

        folded = DashboardV2Service._fold_periods(rows, "mmaa_month")

        self.assertEqual(len(folded), 1)
        self.assertEqual(folded[0]["potentiel"], 300.0)
        self.assertEqual(folded[0]["heures_service"], 150.0)

    def test_regularisation_famille_filter_uses_site_affectations(self):
        """Famille narrowing must go through ``Site.affectations``.

        ``Regularisation_GM`` only links to ``Site``; there is no
        ``Site.code_materiel`` relation, so traversing
        ``code_site__code_materiel__...`` raises FieldError. This locks in the
        working path (and that the join cannot duplicate rows).
        """
        qs = DashboardV2Service._regularisation(
            code_filiale="P",
            date_debut="2026-01-01",
            date_fin="2026-12-31",
            code_famille="A01",
        )

        where, _params = qs.query.sql_with_params()
        self.assertIn("affectation", where)
        self.assertIn("code_famille", where)
        # The join must go through Site -> Affectation, never Site -> materiel.
        self.assertNotIn("code_site_id__code_materiel", where)
        self.assertTrue(qs.query.distinct)

    def test_regularisation_without_famille_only_filters_filiale(self):
        qs = DashboardV2Service._regularisation(
            code_filiale="P", date_debut="2026-01-01", date_fin="2026-12-31"
        )

        where, _params = qs.query.sql_with_params()
        self.assertIn("code_filiale", where)
        self.assertNotIn("affectation", where)

    def test_get_maintenance_merges_mtbf_mttr_cout_into_one_dict(self):
        mtbf = {
            "evolution": [{"mmaa": "2026-01", "heures_service": 100, "nombre_pannes": 5, "mtbf": 20}],
            "breakdown": [self._row("F1", "Famille 1", heures_service=100, nombre_pannes=5, mtbf=20)],
        }
        mttr = {
            "evolution": [{"mmaa": "2026-01", "heures_panne": 10, "interventions_correctives": 2, "mttr": 5}],
            "breakdown": [self._row("F1", "Famille 1", heures_panne=10, interventions_correctives=2, mttr=5)],
        }
        cout = {
            "evolution": [{"mmaa": "2026-01", "heures_panne": 10, "cout_panne": 1000, "records_with_tarif": 2, "records_without_tarif": 0}],
            "breakdown": [self._row("F1", "Famille 1", heures_panne=10, cout_panne=1000, records_with_tarif=2, records_without_tarif=0)],
        }

        def _maintenance_series(qs, niveau, aggregates_factory, numerator, denominator, ratio_name):
            # mtbf uses (heures_service, nombre_pannes, mtbf), mttr uses
            # (heures_panne, interventions_correctives, mttr).
            if numerator == "heures_service":
                return mtbf
            return mttr

        with (
            mock.patch.object(DashboardV2Service, "_pointage_base", return_value=object()),
            mock.patch.object(DashboardV2Service, "_maintenance_series", side_effect=_maintenance_series),
            mock.patch.object(DashboardV2Service, "_cout_panne_series", return_value=cout),
        ):
            result = DashboardV2Service.get_maintenance(
                code_filiale="P",
                date_debut="2026-01-01",
                date_fin="2026-01-31",
                code_famille="",
                niveau="famille",
            )

        # The three sub-series must be merged into one dict.
        self.assertIn("mtbf", result)
        self.assertIn("mttr", result)
        self.assertIn("coutPanne", result)
        self.assertEqual(result["mtbf"], mtbf)
        self.assertEqual(result["mttr"], mttr)
        self.assertEqual(result["coutPanne"], cout)

    def test_get_maintenance_breakdown_rows_share_famille_key(self):
        mtbf = {"evolution": [], "breakdown": [self._row("F1", "Famille 1")]}
        mttr = {"evolution": [], "breakdown": [self._row("F1", "Famille 1")]}
        cout = {"evolution": [], "breakdown": [self._row("F1", "Famille 1")]}

        def _maintenance_series(qs, niveau, aggregates_factory, numerator, denominator, ratio_name):
            return mtbf if numerator == "heures_service" else mttr

        with (
            mock.patch.object(DashboardV2Service, "_pointage_base", return_value=object()),
            mock.patch.object(DashboardV2Service, "_maintenance_series", side_effect=_maintenance_series),
            mock.patch.object(DashboardV2Service, "_cout_panne_series", return_value=cout),
        ):
            result = DashboardV2Service.get_maintenance(
                code_filiale="P",
                date_debut="2026-01-01",
                date_fin="2026-01-31",
                code_famille="",
                niveau="famille",
            )

        self.assertEqual(result["mtbf"]["breakdown"][0]["code"], "F1")
        self.assertEqual(result["mttr"]["breakdown"][0]["code"], "F1")
        self.assertEqual(result["coutPanne"]["breakdown"][0]["code"], "F1")


class DashboardV2FormulasTest(TestCase):
    """Real-query tests for the corrected dashboard v2 formulas.

    Unlike `DashboardV2ServiceTest` (hermetic, mocked) these run the real ORM
    aggregations over a small fixture so the window functions, the
    aggregate-ordering constraints and the sign conventions are all exercised.
    """

    DEBUT = "2026-01-01"
    FIN = "2026-01-31"

    def setUp(self):
        # The rentabilite ranking is memoized for 5 minutes in a process-wide
        # LocMem cache: without this, a ranking computed by a previous test
        # (with its own fixture) would be served to the next one.
        cache.clear()
        user = get_user_model().objects.create(username="tester")
        self.user = user

        self.entreprise = Entreprise.objects.create(
            code_entreprise="E1",
            raison_sociale="Groupe",
            numero_registre_commerce="RC",
            numero_compte_bancaire="CB",
            capital_social=Decimal("1000"),
            date_registre_commerce=date(2020, 1, 1),
            type_dossier="D",
            user_id=user,
        )
        self.filiale_p = Filiale.objects.create(
            code_filiale="P",
            code_entreprise=self.entreprise,
            libelle_filiale="Parente",
            user_id=user,
        )
        self.filiale_f = Filiale.objects.create(
            code_filiale="F",
            code_entreprise=self.entreprise,
            libelle_filiale="Fille",
            user_id=user,
        )
        self.division = Division.objects.create(
            code_division="DV1",
            libelle_division="Division 1",
            code_filiale=self.filiale_p,
            user_id=user,
        )
        self.categorie = Categorie_GM.objects.create(
            code_categorie="CAT1", libelle_categorie="Cat 1", user_id=user
        )
        self.familles = {}
        for code in ("FM1", "FM2"):
            self.familles[code] = Famille_Materiel.objects.create(
                code_famille=code,
                code_categorie_gm=self.categorie,
                libelle_famille=f"Famille {code}",
                user_id=user,
            )
        self.sous_familles = {
            "SF1": Sous_Famille_Materiel.objects.create(
                code_sous_famille="SF1",
                libelle_sous_famille="Sous famille 1",
                code_famille_materiel=self.familles["FM1"],
                user_id=user,
            ),
            "SF2": Sous_Famille_Materiel.objects.create(
                code_sous_famille="SF2",
                libelle_sous_famille="Sous famille 2",
                code_famille_materiel=self.familles["FM2"],
                user_id=user,
            ),
        }
        self.sites = {
            "S1": self._site("S1", "Site 1", self.filiale_p),
            "S2": self._site("S2", "Site 2", self.filiale_p),
        }
        self.type_etat = Type_Etat_Materiel.objects.create(
            code_type_etat_materiel="TE1",
            libelle_type_etat_materiel="Bon",
            user_id=user,
        )
        ta_01 = Type_Affectation.objects.create(
            code_type_affectation="01", libelle_type_affectation="Affectation", user_id=user
        )
        ta_02 = Type_Affectation.objects.create(
            code_type_affectation="02", libelle_type_affectation="ALREM", user_id=user
        )
        ta_04 = Type_Affectation.objects.create(
            code_type_affectation="04", libelle_type_affectation="Reparation", user_id=user
        )
        self.ts_service = Type_Situation.objects.create(
            code_type_situation="01",
            libelle_type_situation="En service",
            code_type_affectation=ta_01,
            user_id=user,
        )
        self.ts_chomage = Type_Situation.objects.create(
            code_type_situation="02",
            libelle_type_situation="En chomage",
            code_type_affectation=ta_01,
            user_id=user,
        )
        self.ts_panne = Type_Situation.objects.create(
            code_type_situation="03",
            libelle_type_situation="En panne",
            code_type_affectation=ta_01,
            user_id=user,
        )
        self.ts_alrem = Type_Situation.objects.create(
            code_type_situation="06",
            libelle_type_situation="ALREM",
            code_type_affectation=ta_02,
            user_id=user,
        )
        self.ts_reparation = Type_Situation.objects.create(
            code_type_situation="04",
            libelle_type_situation="En reparation",
            code_type_affectation=ta_04,
            user_id=user,
        )

    def _site(self, code, libelle, filiale):
        return Site.objects.create(
            code_site=code,
            code_filiale=filiale,
            code_region="R",
            libelle_site=libelle,
            code_agence="A",
            type_site="T",
            numero_ss_employeur="SS",
            code_commune_site="C",
            code_division=self.division,
            user_id=self.user,
        )

    def _materiel(self, code, sous_famille="SF1", date_acquisition=date(2020, 1, 15), filiale=None):
        return Grand_Materiel.objects.create(
            code_materiel=code,
            designation=f"Designation {code}",
            date_acquisition=date_acquisition,
            valeur_acquisition=Decimal("1000"),
            code_sous_famille_materiel=self.sous_familles[sous_famille],
            code_filiale_g=filiale or self.filiale_p,
            user_id=self.user,
        )

    def _affectation(self, materiel, site, date_affectation=datetime(2026, 1, 5, 8, 0), fin=None):
        return Affectation_Materiel.objects.create(
            code_affectation=f"AFF-{materiel.code_materiel}-{site.code_site}",
            code_materiel=materiel,
            code_filiale_mere=self.filiale_p,
            code_site=site,
            date_affectation=date_affectation,
            date_fin_affectation=fin,
            nbr_jours_affectation=30,
            user_id=self.user,
        )

    def _pointage(self, affectation, mmaa=date(2026, 1, 15), **kwargs):
        payload = {
            "heures_service": Decimal("100"),
            "heures_chomage": Decimal("10"),
            "heures_panne": Decimal("5"),
            "potentiel": Decimal("200"),
            "taux_location": Decimal("1000"),
            "date_modification": datetime(2026, 1, 31),
            "user_id": self.user,
        }
        payload.update(kwargs)
        return Pointage.objects.create(
            affectation_id=affectation, mmaa=mmaa, **payload
        )

    def _situation(self, affectation, type_situation, jour=10):
        return Situation_Materiel.objects.create(
            id_situation=f"SIT-{affectation.code_affectation}-{type_situation.code_type_situation}-{jour}",
            affectation_id=affectation,
            type_situation_id=type_situation,
            code_type_etat_materiel=self.type_etat,
            date_situation=datetime(2026, 1, jour, 8, 0),
            user_id=self.user,
        )

    # ------------------------------------------------------------------
    # _ratios: TMAD / TAM / TIP
    # ------------------------------------------------------------------
    def test_ratios_are_three_distinct_metrics(self):
        # potentiel 200, panne 20, chomage 40, service 100
        #   disponibilite = (200-20)/200          = 90
        #   tmad          = (200-20-40)/200       = 70
        #   tam           = 100/(200-20)          = 55.6
        #   tip           = 20/200                = 10
        ratios = DashboardV2Service._ratios(200, 100, 40, 20)
        self.assertEqual(ratios["disponibilite"], 90.0)
        self.assertEqual(ratios["tmad"], 70.0)
        self.assertEqual(ratios["tam"], 55.6)
        self.assertEqual(ratios["tip"], 10.0)
        self.assertNotEqual(ratios["tmad"], ratios["tam"])
        self.assertNotEqual(ratios["tam"], ratios["disponibilite"])
        # taux_chomage / taux_utilisation / rendement keep their definitions.
        self.assertEqual(ratios["taux_chomage"], 20.0)
        self.assertEqual(ratios["taux_utilisation"], 50.0)
        self.assertEqual(ratios["rendement"], 45.0)

    def test_ratios_with_zero_potentiel_are_all_zero(self):
        ratios = DashboardV2Service._ratios(0, 100, 40, 20)
        self.assertEqual(ratios["disponibilite"], 0.0)
        self.assertEqual(ratios["tmad"], 0.0)
        self.assertEqual(ratios["tam"], 0.0)
        self.assertEqual(ratios["tip"], 0.0)
        self.assertEqual(ratios["taux_chomage"], 0.0)

    def test_ratios_with_fleet_fully_down_does_not_divide_by_zero(self):
        # potentiel == heures_panne -> the TAM denominator is 0.
        ratios = DashboardV2Service._ratios(100, 0, 0, 100)
        self.assertEqual(ratios["disponibilite"], 0.0)
        self.assertEqual(ratios["tam"], 0.0)
        self.assertEqual(ratios["tip"], 100.0)

    def test_overview_tamd_tam_tip_differ(self):
        m = self._materiel("MAT-1")
        aff = self._affectation(m, self.sites["S1"])
        self._pointage(
            aff,
            heures_service=Decimal("100"),
            heures_chomage=Decimal("40"),
            heures_panne=Decimal("20"),
            potentiel=Decimal("200"),
        )
        self._situation(aff, self.ts_service)

        mk = DashboardV2Service.get_overview(
            date_debut=self.DEBUT, date_fin=self.FIN
        )["maintenanceKpis"]

        self.assertEqual(mk["disponibilite"], 90.0)
        self.assertEqual(mk["tamd"], 70.0)
        self.assertEqual(mk["tam"], 55.6)
        self.assertEqual(mk["tip"], 10.0)
        # `taux_panne` and `tip` are both heures_panne / potentiel.
        self.assertEqual(mk["taux_panne"], mk["tip"])
        # the backend taux_chomage is used as-is (no frontend recomputation)
        self.assertEqual(mk["taux_chomage"], 20.0)

    # ------------------------------------------------------------------
    # Financials: single CA definition + signed ecart_cible
    # ------------------------------------------------------------------
    def test_overview_financial_kpis_signs(self):
        m1 = self._materiel("MAT-1")
        aff1 = self._affectation(m1, self.sites["S1"])
        # montant_service NULL -> ca_realise = 100 h x 1000 = 100 000
        # potentiel 200 x 1000 = 200 000 (ca_potentiel)
        self._pointage(aff1, montant_service=None, montant_chomage=None, montant_panne=None)

        # Second material: billed above its potential (over-billing).
        m2 = self._materiel("MAT-2")
        aff2 = self._affectation(m2, self.sites["S2"])
        self._pointage(
            aff2,
            heures_service=Decimal("100"),
            potentiel=Decimal("100"),
            montant_service=Decimal("300000"),
            montant_chomage=None,
            montant_panne=None,
        )

        fk = DashboardV2Service.get_overview(
            date_debut=self.DEBUT, date_fin=self.FIN
        )["financialKpis"]

        self.assertEqual(fk["caRealise"], 400000.0)
        self.assertEqual(fk["caPotentiel"], 300000.0)
        # manque_a_gagner is signed: negative == billed above the potential.
        self.assertEqual(fk["manqueAGagner"], -100000.0)
        # ecart_cible is positive-is-good, so over-billing is negative.
        self.assertEqual(fk["ecartCible"], round((300000 - 400000) / 300000 * 100, 1))
        self.assertLess(fk["ecartCible"], 0)
        # total facturé = ca réalisé + chômage + panne
        self.assertEqual(fk["totalFacture"], 400000.0)

    def test_overview_manque_a_gagner_keeps_over_billing(self):
        m = self._materiel("MAT-1")
        aff = self._affectation(m, self.sites["S1"])
        self._pointage(aff, potentiel=Decimal("100"), montant_service=Decimal("250000"))

        fk = DashboardV2Service.get_overview(
            date_debut=self.DEBUT, date_fin=self.FIN
        )["financialKpis"]

        self.assertEqual(fk["caPotentiel"], 100000.0)
        self.assertEqual(fk["caRealise"], 250000.0)
        self.assertEqual(fk["manqueAGagner"], -150000.0)
        self.assertLess(fk["ecartCible"], 0)

    # ------------------------------------------------------------------
    # Rentabilite prorata
    # ------------------------------------------------------------------
    def test_rentabilite_prorata_is_per_site(self):
        m1 = self._materiel("MAT-1")
        m2 = self._materiel("MAT-2")
        aff1 = self._affectation(m1, self.sites["S1"])
        aff2 = self._affectation(m2, self.sites["S2"])
        # 300 h at site 1, 100 h at site 2
        self._pointage(aff1, heures_service=Decimal("300"), taux_location=Decimal("1000"))
        self._pointage(aff2, heures_service=Decimal("100"), taux_location=Decimal("1000"))
        Regularisation_GM.objects.create(
            code_site=self.sites["S1"],
            mmaa=date(2026, 1, 1),
            montant_regularisation=Decimal("40000"),
            user_id=self.user,
        )
        Regularisation_GM.objects.create(
            code_site=self.sites["S2"],
            mmaa=date(2026, 1, 1),
            montant_regularisation=Decimal("10000"),
            user_id=self.user,
        )

        result = DashboardV2Service.get_finances(
            date_debut=self.DEBUT, date_fin=self.FIN, niveau="engin"
        )
        ranking = {row["code_materiel"]: row for row in result["rentabilite"]["ranking"]}

        # The whole regularisation of a site must be allocated inside that site.
        self.assertEqual(ranking["MAT-1"]["regularisation"], 40000.0)
        self.assertEqual(ranking["MAT-2"]["regularisation"], 10000.0)
        self.assertEqual(ranking["MAT-1"]["chiffre_affaires"], 300000.0)
        self.assertEqual(ranking["MAT-1"]["marge"], 260000.0)
        # and the ranking now carries the famille / filiale labels
        self.assertEqual(ranking["MAT-1"]["libelle_famille"], "Famille FM1")
        self.assertEqual(ranking["MAT-1"]["libelle_filiale"], "Parente")

    def test_rentabilite_prorata_within_one_site_is_prorated(self):
        m1 = self._materiel("MAT-1")
        m2 = self._materiel("MAT-2")
        aff1 = self._affectation(m1, self.sites["S1"])
        aff2 = self._affectation(m2, self.sites["S1"])
        self._pointage(aff1, heures_service=Decimal("300"), taux_location=Decimal("1000"))
        self._pointage(aff2, heures_service=Decimal("100"), taux_location=Decimal("1000"))
        Regularisation_GM.objects.create(
            code_site=self.sites["S1"],
            mmaa=date(2026, 1, 1),
            montant_regularisation=Decimal("40000"),
            user_id=self.user,
        )

        result = DashboardV2Service.get_finances(
            date_debut=self.DEBUT, date_fin=self.FIN, niveau="engin"
        )
        ranking = {row["code_materiel"]: row for row in result["rentabilite"]["ranking"]}

        self.assertEqual(ranking["MAT-1"]["regularisation"], 30000.0)
        self.assertEqual(ranking["MAT-2"]["regularisation"], 10000.0)
        self.assertEqual(
            ranking["MAT-1"]["regularisation"] + ranking["MAT-2"]["regularisation"],
            40000.0,
        )

    # ------------------------------------------------------------------
    # Taux d'affectation
    # ------------------------------------------------------------------
    def test_taux_affectation_parc_total_sums_to_parc_for_every_niveau(self):
        m1 = self._materiel("MAT-1")
        m2 = self._materiel("MAT-2", sous_famille="SF2", filiale=self.filiale_f)
        m3 = self._materiel("MAT-3")
        self._affectation(m1, self.sites["S1"])
        self._affectation(m2, self.sites["S2"])
        # m3 is never affected

        parc_total = Grand_Materiel.objects.filter(est_bloque=False).count()
        self.assertEqual(parc_total, 3)

        for niveau in ("engin", "famille", "groupe", "chantier"):
            with self.subTest(niveau=niveau):
                result = DashboardV2Service.get_finances(
                    date_debut=self.DEBUT, date_fin=self.FIN, niveau=niveau
                )
                taux = result["tauxAffectation"]
                summed = sum(row["parc_total"] for row in taux["breakdown"])
                self.assertEqual(summed, parc_total)
                self.assertEqual(taux["global"]["parc_total"], parc_total)
                self.assertEqual(taux["global"]["engins_affectes"], 2)
                self.assertEqual(
                    taux["global"]["taux_affectation"],
                    round(2 / parc_total * 100, 1),
                )

    def test_taux_affectation_evolution_counts_closed_affectations(self):
        m = self._materiel("MAT-1")
        # created in the period but closed: it is a real "mise en affectation"
        self._affectation(
            m,
            self.sites["S1"],
            date_affectation=datetime(2026, 1, 5, 8, 0),
            fin=datetime(2026, 2, 5, 8, 0),
        )
        m2 = self._materiel("MAT-2")
        self._affectation(m2, self.sites["S2"], date_affectation=datetime(2026, 1, 20, 8, 0))

        result = DashboardV2Service.get_finances(
            date_debut=self.DEBUT, date_fin=self.FIN, niveau="engin"
        )
        evolution = result["tauxAffectation"]["evolution"]

        self.assertEqual(len(evolution), 1)
        self.assertEqual(evolution[0]["mmaa"], "2026-01-01")
        # both the closed and the open affectation count as a flow
        self.assertEqual(evolution[0]["engins_affectes"], 2)
        self.assertEqual(evolution[0]["parc_total"], 2)

    # ------------------------------------------------------------------
    # age_moyen around a year boundary
    # ------------------------------------------------------------------
    def test_age_moyen_is_elapsed_years_at_date_fin(self):
        # acquired 2023-12-15 -> 2 full years at 2026-01-31
        self._materiel("MAT-1", date_acquisition=date(2023, 12, 15))
        # acquired 2024-01-15 -> 2 full years at 2026-01-31
        self._materiel("MAT-2", date_acquisition=date(2024, 1, 15))
        # acquired after the period: must be excluded
        self._materiel("MAT-3", date_acquisition=date(2026, 6, 1))
        # no acquisition date: must be excluded
        self._materiel("MAT-4", date_acquisition=None)

        gk = DashboardV2Service.get_overview(
            date_debut=self.DEBUT, date_fin=self.FIN
        )["globalKpis"]

        self.assertEqual(gk["age_moyen"], 2)
        # the material acquired in 2026 is not counted at all
        self.assertEqual(gk["parc_total"], 4)

    # ------------------------------------------------------------------
    # situation population
    # ------------------------------------------------------------------
    def test_situation_total_is_material_scoped(self):
        m1 = self._materiel("MAT-1")
        m2 = self._materiel("MAT-2")
        # m1 has TWO affectations, each with a situation: it must count once
        aff1a = self._affectation(m1, self.sites["S1"], date_affectation=datetime(2025, 1, 5, 8, 0))
        aff1b = self._affectation(m1, self.sites["S2"], date_affectation=datetime(2025, 6, 5, 8, 0))
        aff2 = self._affectation(m2, self.sites["S1"], date_affectation=datetime(2025, 1, 5, 8, 0))
        # m1's latest situation overall is "en panne" (2026-01-20 on aff1b)
        self._situation(aff1a, self.ts_service, jour=10)
        self._situation(aff1b, self.ts_panne, jour=20)
        self._situation(aff2, self.ts_chomage, jour=10)
        # m2 also has an older situation on another affectation (ignored)
        aff2b = self._affectation(m2, self.sites["S2"], date_affectation=datetime(2025, 3, 5, 8, 0))
        self._situation(aff2b, self.ts_service, jour=5)

        result = DashboardV2Service.get_overview(date_debut=self.DEBUT, date_fin=self.FIN)
        gk = result["globalKpis"]
        distribution = DashboardV2Service.get_situation(
            date_debut=self.DEBUT, date_fin=self.FIN
        )["situationDistribution"]

        self.assertEqual(gk["parc_total"], 2)
        # 2 materials, 4 affectation-level situations
        self.assertEqual(gk["situation_total"], 2)
        self.assertEqual(sum(item["count"] for item in distribution), 2)
        self.assertEqual(gk["en_panne"], 1)
        self.assertEqual(gk["en_chomage"], 1)
        self.assertEqual(gk["en_service"], 0)

    # ------------------------------------------------------------------
    # situation distribution: one slice per (affectation, situation) bucket
    # ------------------------------------------------------------------
    def test_situation_distribution_is_grouped_by_situation_bucket(self):
        """One donut slice per bucket, however many materials carry it.

        The window filter used to be combined with the ``Count`` in a single
        query, so Django pulled the window's partition columns into
        ``GROUP BY``: every group became ``count = 1`` and the donut rendered
        one identically-labelled slice per material.
        """
        materials = [self._materiel(f"MAT-{i}") for i in range(1, 5)]
        for i, m in enumerate(materials):
            aff = self._affectation(m, self.sites["S1"])
            self._situation(aff, self.ts_service, jour=10 + i)

        distribution = DashboardV2Service.get_situation(
            date_debut=self.DEBUT, date_fin=self.FIN
        )["situationDistribution"]

        self.assertEqual(len(distribution), 1)
        self.assertEqual(distribution[0]["libelle_type_situation"], "En service")
        # The regression: the 4 materials are summed, not spread over 4 slices.
        self.assertEqual(distribution[0]["count"], 4)

    def test_situation_distribution_splits_by_affectation_situation_pair(self):
        """A situation code shared by two affectation types yields two slices.

        Code ``02`` is "En chômage" under affectation ``01`` ("En exploitation")
        but an *immobilised base* under affectation ``04`` ("Immobilisé"). The
        donut must keep them apart, exactly as the KPI cards do — this is the
        606-vs-476 mismatch.
        """
        ts_chomage_immob = Type_Situation.objects.create(
            code_type_situation="02",
            libelle_type_situation="En chomage",
            code_type_affectation=Type_Affectation.objects.get(
                code_type_affectation="04"
            ),
            user_id=self.user,
        )

        # 2 materials "en chômage" on an exploitation affectation...
        for i in range(2):
            m = self._materiel(f"MAT-E{i}")
            self._situation(
                self._affectation(m, self.sites["S1"]), self.ts_chomage, jour=10 + i
            )
        # ...and 1 material "en chômage" but immobilised.
        m = self._materiel("MAT-I0")
        self._situation(
            self._affectation(m, self.sites["S2"]), ts_chomage_immob, jour=20
        )

        distribution = DashboardV2Service.get_situation(
            date_debut=self.DEBUT, date_fin=self.FIN
        )["situationDistribution"]
        by_label = {r["libelle_type_situation"]: r["count"] for r in distribution}

        # Slice labels come from the BUCKET, not from the raw Type_Situation
        # label (the fixture spells it "En chomage" without the accent).
        self.assertEqual(by_label["En chômage"], 2)
        self.assertEqual(by_label["Immobilisé base"], 1)
        # The two slices must not share a code, or the donut would paint them
        # with the same colour.
        codes = [r["code_type_situation"] for r in distribution]
        self.assertEqual(len(codes), len(set(codes)))

    def test_situation_distribution_matches_the_kpi_cards(self):
        """Every donut slice equals the matching KPI card, and both total the parc."""
        ts_chomage_immob = Type_Situation.objects.create(
            code_type_situation="02",
            libelle_type_situation="En chomage",
            code_type_affectation=Type_Affectation.objects.get(
                code_type_affectation="04"
            ),
            user_id=self.user,
        )
        for i, ts in enumerate(
            [
                self.ts_service,
                self.ts_chomage,
                self.ts_panne,
                self.ts_alrem,
                self.ts_reparation,
                ts_chomage_immob,
            ]
        ):
            m = self._materiel(f"MAT-{i}")
            self._situation(self._affectation(m, self.sites["S1"]), ts, jour=10 + i)

        kpis = DashboardV2Service.get_overview(
            date_debut=self.DEBUT, date_fin=self.FIN
        )["globalKpis"]
        distribution = DashboardV2Service.get_situation(
            date_debut=self.DEBUT, date_fin=self.FIN
        )["situationDistribution"]

        card_by_label = {
            "En service": kpis["en_service"],
            "En chômage": kpis["en_chomage"],
            "En panne": kpis["en_panne"],
            "Immobilisé base": kpis["immobilise_base"],
            "En réparation": kpis["en_reparation"],
            "ALREM": kpis["alrem"],
            "Autres": kpis["autres"],
        }
        for row in distribution:
            self.assertEqual(
                row["count"],
                card_by_label[row["libelle_type_situation"]],
                f"{row['libelle_type_situation']} differs between donut and card",
            )
        # And the buckets cover the whole situation population exactly once.
        self.assertEqual(sum(row["count"] for row in distribution), kpis["situation_total"])

    def test_situation_distribution_total_matches_situation_total(self):
        """The slices must add up to the situation population of the overview."""
        for i, ts in enumerate([self.ts_service, self.ts_chomage, self.ts_panne]):
            m = self._materiel(f"MAT-{i}")
            aff = self._affectation(m, self.sites["S1"])
            self._situation(aff, ts, jour=10 + i)

        distribution = DashboardV2Service.get_situation(
            date_debut=self.DEBUT, date_fin=self.FIN
        )["situationDistribution"]
        overview = DashboardV2Service.get_overview(
            date_debut=self.DEBUT, date_fin=self.FIN
        )

        self.assertEqual(
            sum(r["count"] for r in distribution),
            overview["globalKpis"]["situation_total"],
        )

    # ------------------------------------------------------------------
    # Rendement: niveau-aware breakdown from a single query
    # ------------------------------------------------------------------
    def test_get_rendement_returns_niveau_aware_breakdown(self):
        m1 = self._materiel("MAT-1", sous_famille="SF1")
        m2 = self._materiel("MAT-2", sous_famille="SF2")
        self._pointage(self._affectation(m1, self.sites["S1"]))
        self._pointage(self._affectation(m2, self.sites["S2"]))

        engin = DashboardV2Service.get_rendement(
            date_debut=self.DEBUT, date_fin=self.FIN, niveau="engin"
        )
        famille = DashboardV2Service.get_rendement(
            date_debut=self.DEBUT, date_fin=self.FIN, niveau="famille"
        )

        self.assertEqual([row["code"] for row in engin["breakdown"]], ["MAT-1", "MAT-2"])
        self.assertEqual([row["code"] for row in famille["breakdown"]], ["FM1", "FM2"])
        # the two evolutions are the same series (documented in the service)
        self.assertEqual(engin["pointageEvolution"], engin["rendementEvolution"])
        self.assertEqual(len(engin["pointageEvolution"]), 1)

    # ------------------------------------------------------------------
    # CA series: montants instead of row counts
    # ------------------------------------------------------------------
    def test_ca_series_exposes_amounts(self):
        m1 = self._materiel("MAT-1")
        aff1 = self._affectation(m1, self.sites["S1"])
        self._pointage(aff1, montant_service=Decimal("120000"), taux_location=Decimal("1000"))
        m2 = self._materiel("MAT-2")
        aff2 = self._affectation(m2, self.sites["S2"])
        # no stored amount -> 100 h x 1000 calculated
        self._pointage(aff2, montant_service=None, taux_location=Decimal("1000"))

        ca = DashboardV2Service.get_finances(
            date_debut=self.DEBUT, date_fin=self.FIN, niveau="engin"
        )["caLocationInterne"]

        self.assertEqual(ca["evolution"][0]["ca_stocke"], 120000.0)
        self.assertEqual(ca["evolution"][0]["ca_calculee"], 100000.0)
        self.assertEqual(ca["evolution"][0]["ca_total"], 220000.0)
        self.assertEqual(ca["evolution"][0]["records_with_montant"], 1)
        self.assertEqual(ca["evolution"][0]["records_without_montant"], 1)

    # ------------------------------------------------------------------
    # Cout de panne: weighted hourly rate over the tariffed hours
    # ------------------------------------------------------------------
    def test_cout_panne_exposes_tariffed_hours(self):
        m1 = self._materiel("MAT-1")
        aff1 = self._affectation(m1, self.sites["S1"])
        self._pointage(
            aff1,
            heures_panne=Decimal("10"),
            taux_location=Decimal("1000"),
        )
        m2 = self._materiel("MAT-2")
        aff2 = self._affectation(m2, self.sites["S2"])
        # no tariff: hours counted, cost zero
        self._pointage(aff2, heures_panne=Decimal("90"), taux_location=None)

        cout = DashboardV2Service.get_maintenance(
            date_debut=self.DEBUT, date_fin=self.FIN, niveau="engin"
        )["coutPanne"]

        self.assertEqual(cout["evolution"][0]["heures_panne"], 100.0)
        self.assertEqual(cout["evolution"][0]["heures_panne_avec_tarif"], 10.0)
        self.assertEqual(cout["evolution"][0]["cout_panne"], 10000.0)

    # ------------------------------------------------------------------
    # get_filiale_stats: material axis + famille filter
    # ------------------------------------------------------------------
    def test_filiale_stats_use_material_filiale_and_famille(self):
        m1 = self._materiel("MAT-1", sous_famille="SF1", filiale=self.filiale_p)
        m2 = self._materiel("MAT-2", sous_famille="SF2", filiale=self.filiale_f)
        aff1 = self._affectation(m1, self.sites["S1"])
        self._affectation(m2, self.sites["S2"])
        self._pointage(aff1)

        all_stats = {
            row["code_filiale"]: row
            for row in DashboardV2Service.get_filiale_stats(
                date_debut=self.DEBUT, date_fin=self.FIN
            )
        }
        self.assertEqual(all_stats["P"]["totalMateriel"], 1)
        self.assertEqual(all_stats["F"]["totalMateriel"], 1)
        self.assertEqual(all_stats["P"]["totalAffectations"], 1)
        self.assertEqual(all_stats["F"]["totalAffectations"], 1)
        self.assertEqual(all_stats["P"]["totalHeuresService"], 100.0)
        self.assertEqual(all_stats["F"]["totalHeuresService"], 0.0)

        filtered = DashboardV2Service.get_filiale_stats(
            code_famille="FM1", date_debut=self.DEBUT, date_fin=self.FIN
        )
        self.assertEqual(len(filtered), 2)
        filtered_map = {row["code_filiale"]: row for row in filtered}
        self.assertEqual(filtered_map["P"]["totalMateriel"], 1)
        self.assertEqual(filtered_map["F"]["totalMateriel"], 0)
        self.assertEqual(filtered_map["F"]["totalAffectations"], 0)

        collapsed = DashboardV2Service.get_filiale_stats(code_filiale="F")
        self.assertEqual([row["code_filiale"] for row in collapsed], ["F"])