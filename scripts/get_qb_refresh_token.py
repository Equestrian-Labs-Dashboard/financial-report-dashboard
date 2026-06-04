from intuitlib.client import AuthClient
from intuitlib.enums import Scopes

CLIENT_ID = "PASTE_YOUR_CLIENT_ID_HERE"
CLIENT_SECRET = "PASTE_YOUR_CLIENT_SECRET_HERE"

REDIRECT_URI = "https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl"
ENVIRONMENT = "production"

auth_client = AuthClient(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    environment=ENVIRONMENT,
)

authorization_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])

print("\nSTEP 1: Open this URL in your browser:")
print(authorization_url)

print("\nSTEP 2: Authorize QuickBooks.")
print("STEP 3: Copy the 'code' value from the redirect URL.")
print("STEP 4: Copy the 'realmId' value from the redirect URL.\n")

code = input("Paste code here: ").strip()
realm_id = input("Paste realmId here: ").strip()

auth_client.get_bearer_token(code, realm_id=realm_id)

print("\nSave these values in GitHub Secrets:")
print("QB_REFRESH_TOKEN=", auth_client.refresh_token)
print("QB_REALM_ID=", auth_client.realm_id)
