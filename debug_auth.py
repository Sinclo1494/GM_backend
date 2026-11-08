from rest_framework.test import APIClient
from api.models import ExternalServiceClient
from api.services.external_service_credentials import (
    generate_client_id, generate_client_secret, hash_secret,
)

client = APIClient()
cid = generate_client_id()
secret = generate_client_secret()
obj = ExternalServiceClient.objects.using("default").create(
    name="dbg", client_id=cid, client_secret_hash=hash_secret(secret), is_active=True,
)
r = client.post("/api/auth/service-token/", {"client_id": cid, "client_secret": secret}, format="json")
print("token status:", r.status_code, "has access:", "access" in r.data)
token = r.data["access"]
r2 = client.get("/api/external/analyse-quantitative/?code_filiale=P", HTTP_AUTHORIZATION=f"Bearer {token}")
print("protected status:", r2.status_code, "body:", r2.content[:300])
c = ExternalServiceClient.objects.using("default").get(id=obj.id)
print("client is_active:", c.is_active, "expires_at:", c.expires_at)
print("allowed_filiales count:", c.allowed_filiales.count())