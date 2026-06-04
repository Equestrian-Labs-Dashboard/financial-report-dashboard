import os
from dotenv import load_dotenv

load_dotenv()


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)

    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")

    return value


SHOPIFY_STORE = env("SHOPIFY_STORE")
SHOPIFY_TOKEN = env("SHOPIFY_TOKEN")

QB_CLIENT_ID = env("QB_CLIENT_ID")
QB_CLIENT_SECRET = env("QB_CLIENT_SECRET")
QB_REFRESH_TOKEN = env("QB_REFRESH_TOKEN")
QB_REALM_ID = env("QB_REALM_ID")

BILL_BASE_URL = env("BILL_BASE_URL", "https://gateway.prod.bill.com/connect")
BILL_USERNAME = env("BILL_USERNAME")
BILL_PASSWORD = env("BILL_PASSWORD")
BILL_ORG_ID = env("BILL_ORG_ID")
BILL_DEV_KEY = env("BILL_DEV_KEY")

START_YEAR = int(env("START_YEAR", "2024"))
