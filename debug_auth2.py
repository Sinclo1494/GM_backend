from django.test.utils import setup_test_environment, teardown_test_environment
from django.test.runner import DiscoverRunner
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from api.models import (
    Entreprise, Division, Filiale, Categorie_GM, Famille_Materiel,
    Sous_Famille_Materiel, Type_Etat_Materiel, Type_Affectation,
    Type_Situation, Site, ExternalServiceClient,
)
from api.services.external_service_credentials import (
    generate_client_id, generate_client_secret, hash_secret,
)

User = get_user_model()
runner = DiscoverRunner(verbosity=0)
setup_test_environment()
old_config = runner.setup_databases()
try:
    user = User.objects.create(username="dbg")
    ent = Entreprise.objects.using("default").create(
        code_entreprise="E1", raison_sociale="Groupe",
        numero_registre_commerce="RC", numero_compte_bancaire="CB",
        capital_social=1000, date_registre_commerce="2020-01-01",
        type_dossier="D", user_id=user,
    )
    fil = Filiale.objects.using("default").create(
        code_filiale="P", code_entreprise=ent, libelle_filiale="Parente",
        user_id=user,
    )
    client = APIClient()
    cid = generate_client_id()
    secret = generate_client_secret()
    obj = ExternalServiceClient.objects.using("default").create(
        name="dbg", client_id=cid, client_secret_hash=hash_secret(secret), is_active=True,
    )
    obj.allowed_filiales.add(fil)
    r = client.post("/api/auth/service-token/", {"client_id": cid, "client_secret": secret}, format="json")
    print("token status:", r.status_code, "has access:", "access" in r.data)
    token = r.data["access"]
    r2 = client.get("/api/external/analyse-quantitative/?code_filiale=P", HTTP_AUTHORIZATION=f"Bearer {token}")
    print("protected status:", r2.status_code, "body:", r2.content[:400])
    r3 = client.get("/api/external/analyse-quantitative/?code_filiale=P", HTTP_AUTHORIZATION=f"Bearer {token}")
    print("again:", r3.status_code)
finally:
    runner.teardown_databases(old_config)
    teardown_test_environment()