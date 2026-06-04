import requests
import config


def login() -> str:
    response = requests.post(
        f"{config.BILL_BASE_URL}/v3/login",
        json={
            "username": config.BILL_USERNAME,
            "password": config.BILL_PASSWORD,
            "organizationId": config.BILL_ORG_ID,
            "devKey": config.BILL_DEV_KEY,
        },
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=45,
    )

    response.raise_for_status()
    data = response.json()

    session_id = (
        data.get("sessionId")
        or data.get("session_id")
        or data.get("response_data", {}).get("sessionId")
    )

    if not session_id:
        raise RuntimeError("BILL login succeeded but no sessionId was returned.")

    return session_id


def get_invoices(year: int) -> list[dict]:
    session_id = login()

    headers = {
        "Accept": "application/json",
        "sessionId": session_id,
        "devKey": config.BILL_DEV_KEY,
    }

    invoices = []
    next_page = None

    while True:
        params = {
            "max": 100,
            "filters": f"invoiceDate:gte:{year}-01-01,invoiceDate:lte:{year}-12-31",
        }

        if next_page:
            params["page"] = next_page

        response = requests.get(
            f"{config.BILL_BASE_URL}/v3/invoices",
            headers=headers,
            params=params,
            timeout=45,
        )

        response.raise_for_status()
        data = response.json()

        items = (
            data.get("results")
            or data.get("invoices")
            or data.get("response_data", [])
            or []
        )

        invoices.extend(items)

        next_page = data.get("nextPage")
        if not next_page:
            break

    return invoices


def normalize_invoices(invoices: list[dict], year: int) -> list[dict]:
    rows = []

    for invoice in invoices:
        invoice_date = invoice.get("invoiceDate", "")

        amount = (
            invoice.get("amount")
            or invoice.get("totalAmount")
            or invoice.get("invoiceAmount")
            or 0
        )

        rows.append({
            "date": invoice_date,
            "year": year,
            "month": invoice_date[5:7] if len(invoice_date) >= 7 else "",
            "source": "BILL",
            "channel": "BILL / B2B",
            "revenue": float(amount or 0),
            "subtotal": float(amount or 0),
            "tax": 0,
            "discounts": 0,
            "status": invoice.get("status", ""),
            "transactions": 1,
        })

    return rows
