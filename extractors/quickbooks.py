import base64
import os
import re
from datetime import date
from typing import Any
from urllib.parse import quote

import requests

QB_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QB_MINOR_VERSION = os.getenv("QB_MINOR_VERSION", "75")

# IMPORTANT:
# This project is using Intuit Development/Sandbox credentials.
# Sandbox access tokens must call the sandbox base URL. If we call the production
# base URL with a sandbox token, QuickBooks returns HTTP 403:
# ApplicationAuthorizationFailed / errorCode=003100.
QB_ENVIRONMENT = os.getenv("QB_ENVIRONMENT", "sandbox").strip().lower()
QB_API_BASE = os.getenv("QB_API_BASE", "").strip()

if not QB_API_BASE:
    if QB_ENVIRONMENT in {"prod", "production", "live"}:
        QB_API_BASE = "https://quickbooks.api.intuit.com"
    else:
        QB_API_BASE = "https://sandbox-quickbooks.api.intuit.com"

DEFAULT_SHIPPING_KEYWORDS = [
    "shipping",
    "shipping cost",
    "shipping expense",
    "postage",
    "freight",
    "delivery",
    "carrier",
    "fulfillment",
    "fulfilment",
    "shipstation",
    "shippo",
    "ups",
    "usps",
    "fedex",
    "dhl",
    "stamps",
]

DEFAULT_EXCLUDE_KEYWORDS = [
    "shipping income",
    "shipping revenue",
    "shipping charges income",
    "shipping charges",
    "sales",
    "income",
    "revenue",
]


def _empty_months() -> dict[str, float]:
    return {f"{month:02d}": 0.0 for month in range(1, 13)}


def _safe_float(value: Any) -> float:
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("$", "").strip()
            if value in {"", "-"}:
                return 0.0
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _keyword_list(env_name: str, default: list[str]) -> list[str]:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return default
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def _normalize(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _is_shipping_cost_label(label: str) -> bool:
    clean = _normalize(label)
    if not clean:
        return False

    keywords = _keyword_list("QB_SHIPPING_COST_KEYWORDS", DEFAULT_SHIPPING_KEYWORDS)
    exclude = _keyword_list("QB_SHIPPING_COST_EXCLUDE_KEYWORDS", DEFAULT_EXCLUDE_KEYWORDS)

    if any(item in clean for item in exclude):
        return False

    return any(item in clean for item in keywords)


def _month_date_range(year: int, month: int) -> tuple[str, str]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1).replace(day=1)
        # go one day back
        from datetime import timedelta
        end = end - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    response = requests.post(
        QB_TOKEN_URL,
        headers={
            "Authorization": f"Basic {auth}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=60,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            "QuickBooks token refresh failed. "
            f"HTTP {response.status_code}: {response.text[:500]}"
        )

    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError(f"QuickBooks token refresh did not return access_token: {payload}")

    return access_token


def qb_get(access_token: str, realm_id: str, path: str, params: dict | None = None) -> dict:
    url = f"{QB_API_BASE}{path}"
    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        params=params or {},
        timeout=90,
    )

    if response.status_code >= 400:
        raise RuntimeError(f"QuickBooks GET failed {path}. HTTP {response.status_code}: {response.text[:500]}")

    return response.json()


def qb_query(access_token: str, realm_id: str, query: str) -> dict:
    path = f"/v3/company/{realm_id}/query"
    # QuickBooks query endpoint accepts query as a URL parameter.
    return qb_get(
        access_token=access_token,
        realm_id=realm_id,
        path=path,
        params={
            "query": query,
            "minorversion": QB_MINOR_VERSION,
        },
    )


def _report_col_amount(col_data: list[dict]) -> float:
    # ProfitAndLoss rows usually store account name in ColData[0] and amount in ColData[-1].
    if not col_data:
        return 0.0
    return _safe_float((col_data[-1] or {}).get("value"))


def _row_label(row: dict) -> str:
    header = row.get("Header") or {}
    col_data = header.get("ColData") or row.get("ColData") or []
    parts = []
    for item in col_data:
        value = (item or {}).get("value")
        if value:
            parts.append(str(value))
    return " | ".join(parts)


def _walk_report_rows(rows: list[dict], matches: list[tuple[str, float]]) -> None:
    for row in rows or []:
        label = _row_label(row)

        # If this row itself has an amount and matches the shipping account name, use it.
        amount = _report_col_amount(row.get("ColData") or [])
        if label and amount and _is_shipping_cost_label(label):
            matches.append((label, abs(amount)))

        # Walk nested rows recursively.
        nested = ((row.get("Rows") or {}).get("Row") or [])
        if nested:
            _walk_report_rows(nested, matches)


def get_shipping_from_profit_and_loss(access_token: str, realm_id: str, year: int, month: int) -> tuple[float, list[str]]:
    start_date, end_date = _month_date_range(year, month)
    data = qb_get(
        access_token=access_token,
        realm_id=realm_id,
        path=f"/v3/company/{realm_id}/reports/ProfitAndLoss",
        params={
            "start_date": start_date,
            "end_date": end_date,
            "accounting_method": os.getenv("QB_ACCOUNTING_METHOD", "Accrual"),
            "minorversion": QB_MINOR_VERSION,
        },
    )

    matches: list[tuple[str, float]] = []
    _walk_report_rows(((data.get("Rows") or {}).get("Row") or []), matches)
    return sum(amount for _, amount in matches), [f"{label}={round(amount, 2)}" for label, amount in matches]


def _line_account_label(line: dict) -> str:
    details = (
        line.get("AccountBasedExpenseLineDetail")
        or line.get("ItemBasedExpenseLineDetail")
        or {}
    )
    account_ref = details.get("AccountRef") or {}
    item_ref = details.get("ItemRef") or {}
    parts = [
        account_ref.get("name"),
        account_ref.get("value"),
        item_ref.get("name"),
        item_ref.get("value"),
        line.get("Description"),
    ]
    return " | ".join(str(part) for part in parts if part)


def _sum_shipping_lines_from_entities(entities: list[dict]) -> tuple[float, list[str]]:
    total = 0.0
    matches = []
    for entity in entities or []:
        txn_date = entity.get("TxnDate", "")
        doc = entity.get("DocNumber") or entity.get("Id") or ""
        for line in entity.get("Line") or []:
            label = _line_account_label(line)
            amount = abs(_safe_float(line.get("Amount")))
            if amount and _is_shipping_cost_label(label):
                total += amount
                matches.append(f"{txn_date} {doc} {label}={round(amount, 2)}")
    return total, matches


def _query_all(access_token: str, realm_id: str, entity: str, start_date: str, end_date: str) -> list[dict]:
    rows = []
    start_position = 1
    page_size = 1000

    while True:
        query = (
            f"SELECT * FROM {entity} "
            f"WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' "
            f"STARTPOSITION {start_position} MAXRESULTS {page_size}"
        )
        data = qb_query(access_token=access_token, realm_id=realm_id, query=query)
        query_response = data.get("QueryResponse") or {}
        batch = query_response.get(entity) or []
        rows.extend(batch)

        if len(batch) < page_size:
            break
        start_position += page_size

    return rows


def get_shipping_from_transactions(access_token: str, realm_id: str, year: int, month: int) -> tuple[float, list[str]]:
    start_date, end_date = _month_date_range(year, month)
    total = 0.0
    matches = []

    # Purchase and Bill are the most common places where shipping expenses live.
    # VendorCredit is subtracted if posted to the same shipping account.
    for entity, sign in [("Purchase", 1), ("Bill", 1), ("VendorCredit", -1)]:
        try:
            entities = _query_all(access_token, realm_id, entity, start_date, end_date)
            entity_total, entity_matches = _sum_shipping_lines_from_entities(entities)
            total += sign * entity_total
            matches.extend([f"{entity}: {item}" for item in entity_matches])
        except Exception as exc:
            print(f"QuickBooks {entity} shipping query skipped for {year}-{month:02d}: {exc}")

    return max(total, 0.0), matches


def get_qb_shipping_costs(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    realm_id: str,
    year: int,
) -> dict[str, float]:
    """
    Returns QuickBooks shipping cost by month.

    Priority:
    1. Profit & Loss rows where account/category label matches shipping cost keywords.
    2. Purchase/Bill/VendorCredit line accounts matching shipping cost keywords.

    Important: this returns company shipping COST only. It never uses Shopify Shipping Charges.
    """
    result = _empty_months()

    if not all([client_id, client_secret, refresh_token, realm_id]):
        print("QuickBooks shipping skipped: missing credentials.")
        return result

    print(f"QuickBooks API base URL: {QB_API_BASE}")
    access_token = refresh_access_token(client_id, client_secret, refresh_token)

    for month in range(1, 13):
        month_key = f"{month:02d}"
        pl_total = 0.0
        tx_total = 0.0
        pl_matches: list[str] = []
        tx_matches: list[str] = []

        try:
            pl_total, pl_matches = get_shipping_from_profit_and_loss(access_token, realm_id, year, month)
        except Exception as exc:
            print(f"QuickBooks P&L shipping lookup failed for {year}-{month_key}: {exc}")

        try:
            tx_total, tx_matches = get_shipping_from_transactions(access_token, realm_id, year, month)
        except Exception as exc:
            print(f"QuickBooks transaction shipping lookup failed for {year}-{month_key}: {exc}")

        # Prefer P&L if it has shipping expense; otherwise use transaction line search.
        chosen = pl_total if pl_total > 0 else tx_total
        result[month_key] = round(chosen, 2)

        if chosen > 0:
            source = "P&L" if pl_total > 0 else "Transactions"
            sample = (pl_matches if pl_total > 0 else tx_matches)[:5]
            print(f"QuickBooks shipping cost {year}-{month_key}: {round(chosen, 2)} from {source}. Matches: {sample}")
        else:
            print(f"QuickBooks shipping cost {year}-{month_key}: 0. No matching shipping expense account/line found.")

    print(f"QuickBooks shipping cost total {year}: {round(sum(result.values()), 2)}")
    return result
