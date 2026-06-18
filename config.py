import os
from dotenv import load_dotenv

load_dotenv()


def required_env(name: str) -> str:
    value = os.getenv(name)

    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")

    return value


def optional_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)

    if value == "":
        return default

    return value


SHOPIFY_STORES = {
    "Corro": {
        "store": required_env("CORRO_SHOPIFY_STORE"),
        "token": required_env("CORRO_SHOPIFY_TOKEN"),
    },
    "Cavali": {
        "store": required_env("CAVALI_SHOPIFY_STORE"),
        "token": required_env("CAVALI_SHOPIFY_TOKEN"),
    },
}

QB_CLIENT_ID = optional_env("QB_CLIENT_ID")
QB_CLIENT_SECRET = optional_env("QB_CLIENT_SECRET")
QB_REFRESH_TOKEN = optional_env("QB_REFRESH_TOKEN")
QB_REALM_ID = optional_env("QB_REALM_ID")

BILL_BASE_URL = optional_env("BILL_BASE_URL", "https://gateway.prod.bill.com/connect")
BILL_USERNAME = optional_env("BILL_USERNAME")
BILL_PASSWORD = optional_env("BILL_PASSWORD")
BILL_ORG_ID = optional_env("BILL_ORG_ID")
BILL_DEV_KEY = optional_env("BILL_DEV_KEY")

START_YEAR = int(optional_env("START_YEAR", "2024"))
