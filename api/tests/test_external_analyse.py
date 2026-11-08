from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import (
        Affectation_Materiel,
        Categorie_GM,
        Division,
        Entreprise,
        Famille_Materiel,
        Filiale,
        Grand_Materiel,
        Pointage,
        Site,
        Situation_Materiel,
        Sous_Famille_Materiel,
        Type_Affectation,
        Type_Etat_Materiel,
        Type_Situation,
    )
from api.models.external_service_client import ExternalServiceClient
from api.services.external_service_credentials import (
    generate_client_id,
    generate_client_secret,
    hash_secret,
)

User = get_user_model()
BASE = "/api/external"
DEBUT = "2026-01-01"
FIN = "2026-01-31"


class _FixtureMixin(TestCase):
    databases = {"default", "filiale_P", "filiale_A"}
    """Shared analyse/journal fixture: two filiales, two sous-familles."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username="tester")
        self.entreprise = Entreprise.objects.create(
            code_entreprise="E1",
            raison_sociale="Groupe",
            numero_registre_commerce="RC",
            numero_compte_bancaire="CB",
            capital_social=Decimal("1000"),
            date_registre_commerce=date(2020, 1, 1),
            type_dossier="D",
            user_id=self.user,
        )
        self.filiale_p = Filiale.objects.create(
            code_filiale="P", code_entreprise=self.entreprise,
            libelle_filiale="Parente", user_id=self.user,
        )
        self.filiale_a = Filiale.objects.create(
            code_filiale="A", code_entreprise=self.entreprise,
            libelle_filiale="Fille", user_id=self.user,
        )
        self.division = Division.objects.create(
            code_division="DV1", libelle_division="Division 1",
            code_filiale=self.filiale_p, user_id=self.user,
        )
        self.categorie = Categorie_GM.objects.create(
            code_categorie="CAT1", libelle_categorie="Cat 1", user_id=self.user,
        )
        self.famille = Famille_Materiel.objects.create(
            code_famille="FM1", code_categorie_gm=self.categorie,
            libelle_famille="Famille 1", user_id=self.user,
        )
        self.sous_famille = Sous_Famille_Materiel.objects.create(
            code_sous_famille="SF1", libelle_sous_famille="Sous famille 1",
            code_famille_materiel=self.famille, user_id=self.user,
        )
        self.site = Site.objects.create(
            code_site="S1", code_filiale=self.filiale_p, code_region="R",
            libelle_site="Site 1", code_agence="A", type_site="T",
            numero_ss_employeur="SS", code_commune_site="C",
            code_division=self.division, user_id=self.user,
        )
        self.type_etat = Type_Etat_Materiel.objects.create(
            code_type_etat_materiel="TE1", libelle_type_etat_materiel="Bon",
            user_id=self.user,
        )
        self.ta_01 = Type_Affectation.objects.create(
            code_type_affectation="01", libelle_type_affectation="Affectation",
            user_id=self.user,
        )
        self.ts_service = Type_Situation.objects.create(
            code_type_situation="01", libelle_type_situation="En service",
            code_type_affectation=self.ta_01, user_id=self.user,
        )

    def _materiel(self, code, filiale):
        return Grand_Materiel.objects.create(
            code_materiel=code,
            designation=f"Designation {code}",
            date_acquisition=date(2020, 1, 15),
            valeur_acquisition=Decimal("1000"),
            code_sous_famille_materiel=self.sous_famille,
            code_filiale_g=filiale,
            user_id=self.user,
        )

    def _affectation(self, materiel, site, date_affectation=datetime(2026, 1, 5, 8, 0), filiale=None):
        return Affectation_Materiel.objects.create(
            code_affectation=f"AFF-{materiel.code_materiel}-{site.code_site}",
            code_materiel=materiel,
            code_filiale_mere=filiale or self.filiale_p,
            code_site=site,
            date_affectation=date_affectation,
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
        return Pointage.objects.create(affectation_id=affectation, mmaa=mmaa, **payload)

    def _situation(self, affectation, type_situation, jour=10):
        return Situation_Materiel.objects.create(
            id_situation=f"SIT-{affectation.code_affectation}-{type_situation.code_type_situation}-{jour}",
            affectation_id=affectation,
            type_situation_id=type_situation,
            code_type_etat_materiel=self.type_etat,
            date_situation=datetime(2026, 1, jour, 8, 0),
            user_id=self.user,
        )

    def _service(self, name="svc", allowed=None):
        cid = generate_client_id()
        secret = generate_client_secret()
        obj = ExternalServiceClient.objects.using("default").create(
            name=name, client_id=cid,
            client_secret_hash=hash_secret(secret), is_active=True,
        )
        if allowed:
            obj.allowed_filiales.set(allowed)
        return obj, secret

    def _auth(self, client_obj, secret):
        resp = self.client.post(
            "/api/auth/service-token/",
            {"client_id": client_obj.client_id, "client_secret": secret},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")


class FilialePermissionTests(_FixtureMixin):
    databases = {"default", "filiale_P", "filiale_A"}
    """External service filiale scoping after the allowed_filiales field."""

    def test_legacy_client_has_all_configured_filiales(self):
        # The data migration back-fills every pre-existing client with all
        # configured filiales. Create a client with an empty set, run the
        # migration's logic, and assert it lands in the back-filled set.
        import importlib

        from django.apps import apps as django_apps

        for code in ["A", "C", "E", "G", "K", "L", "M", "P", "R", "T"]:
            Filiale.objects.using("default").get_or_create(
                code_filiale=code,
                defaults={
                    "libelle_filiale": f"Filiale {code}",
                    "code_entreprise": self.entreprise,
                    "user_id": self.user,
                },
            )
        obj, secret = self._service(name="legacy")
        self.assertEqual(list(obj.allowed_filiales.all()), [])

        migration = importlib.import_module(
            "api.migrations.0032_externalserviceclient_grant_existing_filiales"
        )
        migration._grant_all_filiales(apps=django_apps, schema_editor=None)
        obj.refresh_from_db(using="default")
        self.assertEqual(
            sorted(f.code_filiale for f in obj.allowed_filiales.all()),
            sorted(["A", "C", "E", "G", "K", "L", "M", "P", "R", "T"]),
        )

    def test_new_client_has_no_filiales(self):
        obj, secret = self._service(name="fresh")
        self.assertEqual(list(obj.allowed_filiales.all()), [])

    def test_unauthorized_filiale_returns_400(self):
        obj, secret = self._service(name="scoped", allowed=[self.filiale_p])
        self._auth(obj, secret)
        resp = self.client.get(f"{BASE}/analyse-quantitative/?code_filiale=F")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json(), {"error": "Code filiale invalide ou non autorisé"})

    def test_authorized_filiale_returns_200(self):
        obj, secret = self._service(name="scoped", allowed=[self.filiale_p])
        self._auth(obj, secret)
        resp = self.client.get(f"{BASE}/analyse-quantitative/?code_filiale=P")
        self.assertEqual(resp.status_code, 200)

    def test_unauthorized_filiale_on_journal(self):
        obj, secret = self._service(name="scoped", allowed=[self.filiale_p])
        self._auth(obj, secret)
        resp = self.client.get(f"{BASE}/journal-materiel/?code_filiale=F")
        self.assertEqual(resp.status_code, 400)

    def test_no_filiale_param_returns_400_for_scoped_client(self):
        obj, secret = self._service(name="scoped", allowed=[self.filiale_p])
        self._auth(obj, secret)
        resp = self.client.get(f"{BASE}/analyse-quantitative/")
        self.assertEqual(resp.status_code, 400)

    def test_legacy_client_can_request_any_filiale(self):
        # A legacy client (back-filled by the data migration with every
        # configured filiale) may request any filiale.
        for code in ["A", "C", "E", "G", "K", "L", "M", "P", "R", "T"]:
            Filiale.objects.using("default").get_or_create(
                code_filiale=code,
                defaults={
                    "libelle_filiale": f"Filiale {code}",
                    "code_entreprise": self.entreprise,
                    "user_id": self.user,
                },
            )
        obj, secret = self._service(name="legacy")
        from django.apps import apps as django_apps
        import importlib
        migration = importlib.import_module(
            "api.migrations.0032_externalserviceclient_grant_existing_filiales"
        )
        migration._grant_all_filiales(apps=django_apps, schema_editor=None)
        self._auth(obj, secret)
        resp = self.client.get(f"{BASE}/analyse-quantitative/?code_filiale=P")
        self.assertEqual(resp.status_code, 200)


class AuthAndReadOnlyTests(_FixtureMixin):
    databases = {"default", "filiale_P", "filiale_A"}
    def test_missing_token_returns_401(self):
        resp = self.client.get(f"{BASE}/analyse-quantitative/?code_filiale=P")
        self.assertEqual(resp.status_code, 401)

    def test_non_get_returns_403(self):
        obj, secret = self._service(name="svc", allowed=[self.filiale_p])
        self._auth(obj, secret)
        for method in ("post", "put", "patch", "delete"):
            resp = getattr(self.client, method)(f"{BASE}/analyse-quantitative/?code_filiale=P")
            self.assertEqual(resp.status_code, 403, method)

    def test_invalid_filiale_code_returns_400(self):
        obj, secret = self._service(name="svc", allowed=[self.filiale_p])
        self._auth(obj, secret)
        resp = self.client.get(f"{BASE}/analyse-quantitative/?code_filiale=Z")
        self.assertEqual(resp.status_code, 400)


class AnalyseQuantitativeTests(_FixtureMixin):
    databases = {"default", "filiale_P", "filiale_A"}
    def _setup_data(self, code_filiale):
        m = self._materiel("M1", self.filiale_p)
        a = self._affectation(m, self.site)
        self._situation(a, self.ts_service)
        self._pointage(a)

    def test_detailed_returns_rows(self):
        self._setup_data("P")
        obj, secret = self._service(name="svc", allowed=[self.filiale_p])
        self._auth(obj, secret)
        resp = self.client.get(
            f"{BASE}/analyse-quantitative/?code_filiale=P&date_debut={DEBUT}&date_fin={FIN}"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertTrue(any(r["code_sous_famille"] == "SF1" for r in data))

    def test_recap_single_filiale(self):
        self._setup_data("P")
        obj, secret = self._service(name="svc", allowed=[self.filiale_p])
        self._auth(obj, secret)
        resp = self.client.get(
            f"{BASE}/analyse-quantitative-recap/?code_filiale=P&date_debut={DEBUT}&date_fin={FIN}"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("nombre_totale", data)
        self.assertIn("age_moyen", data)
        self.assertIn("exploitation", data)
        self.assertEqual(data["exploitation"]["en_service"], 100)


class AnalyseExploitationTests(_FixtureMixin):
    databases = {"default", "filiale_P", "filiale_A"}
    def _setup_data(self):
        m = self._materiel("M1", self.filiale_p)
        a = self._affectation(m, self.site)
        self._situation(a, self.ts_service)
        self._pointage(a)

    def test_detailed_returns_rows(self):
        self._setup_data()
        obj, secret = self._service(name="svc", allowed=[self.filiale_p])
        self._auth(obj, secret)
        resp = self.client.get(
            f"{BASE}/analyse-exploitation/?code_filiale=P&date_debut={DEBUT}&date_fin={FIN}"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        row = next(r for r in data if r["code_sous_famille"] == "SF1")
        self.assertEqual(row["heures_service"], 100)
        self.assertEqual(row["heures_chomage"], 10)
        self.assertEqual(row["heures_panne"], 5)
        self.assertEqual(row["nbr_pointage"], 1)

    def test_recap_single_filiale(self):
        self._setup_data()
        obj, secret = self._service(name="svc", allowed=[self.filiale_p])
        self._auth(obj, secret)
        resp = self.client.get(
            f"{BASE}/analyse-exploitation-recap/?code_filiale=P&date_debut={DEBUT}&date_fin={FIN}"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["heures_service"], 100)
        self.assertEqual(data["heures_chomage"], 10)
        self.assertEqual(data["heures_panne"], 5)
        self.assertEqual(data["nombre_pointage"], 1)
        self.assertEqual(data["nombre_existant"], 1)
        self.assertAlmostEqual(data["pct_heures_service"], 100.0 * 100 / 115, places=1)

def test_recap_all_filiales_weighted(self):
        # Same data in two filiales -> every counter doubles; percentages
        # recomputed from combined totals, not averaged.
        site_f = Site.objects.create(
            code_site="S2", code_filiale=self.filiale_a, code_region="R",
            libelle_site="Site 2", code_agence="A", type_site="T",
            numero_ss_employeur="SS", code_commune_site="C",
            code_division=self.division, user_id=self.user,
        )
        m1 = self._materiel("M1", self.filiale_p)
        a1 = self._affectation(m1, self.site)
        self._situation(a1, self.ts_service)
        self._pointage(a1)

        m2 = self._materiel("M2", self.filiale_a)
        a2 = self._affectation(m2, site_f, filiale=self.filiale_a)
        self._situation(a2, self.ts_service)
        self._pointage(a2)

        obj, secret = self._service(name="svc", allowed=[self.filiale_p, self.filiale_a])
        self._auth(obj, secret)
        resp = self.client.get(
            f"{BASE}/analyse-exploitation-recap/?date_debut={DEBUT}&date_fin={FIN}"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["heures_service"], 200)
        self.assertEqual(data["heures_chomage"], 20)
        self.assertEqual(data["heures_panne"], 10)
        self.assertEqual(data["nombre_pointage"], 2)
        self.assertAlmostEqual(data["pct_heures_service"], 100.0 * 200 / 230, places=1)


class JournalMaterielTests(_FixtureMixin):
    databases = {"default", "filiale_P", "filiale_A"}
    def _setup_materiel(self, code, filiale, designation="Designation X"):
        return Grand_Materiel.objects.create(
            code_materiel=code,
            designation=designation,
            date_acquisition=date(2020, 1, 15),
            valeur_acquisition=Decimal("1000"),
            code_sous_famille_materiel=self.sous_famille,
            code_filiale_g=filiale,
            user_id=self.user,
        )

    def test_single_filiale_paginated(self):
        self._setup_materiel("M1", self.filiale_p)
        self._setup_materiel("M2", self.filiale_p)
        obj, secret = self._service(name="svc", allowed=[self.filiale_p])
        self._auth(obj, secret)
        resp = self.client.get(
            f"{BASE}/journal-materiel/?code_filiale=P&page=1&page_size=1"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["results"]), 1)
        self.assertIn("code_materiel", data["results"][0])

    def test_all_filiales_global_count(self):
        self._setup_materiel("M1", self.filiale_p)
        self._setup_materiel("M2", self.filiale_a)
        obj, secret = self._service(name="svc", allowed=[self.filiale_p, self.filiale_a])
        self._auth(obj, secret)
        resp = self.client.get(f"{BASE}/journal-materiel/?page=1&page_size=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["results"]), 2)

    def test_filter_by_designation(self):
        self._setup_materiel("M1", self.filiale_p, designation="Tracteur")
        self._setup_materiel("M2", self.filiale_p, designation="Moissonneuse")
        obj, secret = self._service(name="svc", allowed=[self.filiale_p])
        self._auth(obj, secret)
        resp = self.client.get(
            f"{BASE}/journal-materiel/?code_filiale=P&designation=Tracteur"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["designation"], "Tracteur")

    def test_ordering_deterministic_across_filiales(self):
        self._setup_materiel("B", self.filiale_p)
        self._setup_materiel("A", self.filiale_a)
        obj, secret = self._service(name="svc", allowed=[self.filiale_p, self.filiale_a])
        self._auth(obj, secret)
        resp = self.client.get(f"{BASE}/journal-materiel/?ordering=code_materiel")
        self.assertEqual(resp.status_code, 200)
        codes = [r["code_materiel"] for r in resp.json()["results"]]
        self.assertEqual(codes, sorted(codes))

    def test_unauthorized_filiale_on_journal_400(self):
        self._setup_materiel("M1", self.filiale_p)
        obj, secret = self._service(name="svc", allowed=[self.filiale_p])
        self._auth(obj, secret)
        resp = self.client.get(f"{BASE}/journal-materiel/?code_filiale=F")
        self.assertEqual(resp.status_code, 400)

    def test_empty_result(self):
        obj, secret = self._service(name="svc", allowed=[self.filiale_p])
        self._auth(obj, secret)
        resp = self.client.get(
            f"{BASE}/journal-materiel/?code_filiale=P&designation=NOPE"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 0)


class MgtDashboardRegressionTests(_FixtureMixin):
    databases = {"default", "filiale_P", "filiale_A"}
    """The four existing MGT endpoints must behave exactly as before."""

    def _setup_pointage(self):
        m = self._materiel("M1", self.filiale_p)
        a = self._affectation(m, self.site)
        self._situation(a, self.ts_service)
        return self._pointage(a)

    def test_legacy_service_can_access_mgt_decadaire(self):
        self._setup_pointage()
        obj, secret = self._service(name="legacy")
        self._auth(obj, secret)
        resp = self.client.get(
            "/api/mgt-dashboard/decadaire/?code_filiale=P&mmaa=202601&decade=1"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.json())
