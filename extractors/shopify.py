import time
import requests

API_VERSION = "2026-01"


def request_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    last_response = None

    for attempt in range(5):
        response = requests.request(method, url, timeout=45, **kwargs)
        last_response = response

        if response.status_code in [429, 500, 502, 503, 504]:
            wait_seconds = 2 ** attempt
            print(f"Shopify retry {attempt + 1}/5. Waiting {wait_seconds}s...")
            time.sleep(wait_seconds)
            continue

        response.raise_for_status()
        return response

    last_response.raise_for_status()
    return last_response


def get_orders(brand: str, store: str, token: str, year: int) -> list[dict]:
    start_date = f"{year}-01-01T00:00:00Z"
    end_date = f"{year}-12-31T23:59:59Z"

    url = f"https://{store}/admin/api/{API_VERSION}/orders.json"

    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    }

    params = {
        "status": "any",
        "created_at_min": start_date,
        "created_at_max": end_date,
        "limit": 250,
        "fields": (
            "id,created_at,total_price,subtotal_price,total_tax,"
            "total_discounts,total_shipping_price_set,source_name,"
            "financial_status,line_items,refunds,currency"
        ),
    }

    orders = []

    while url:
        response = request_with_retry("GET", url, headers=headers, params=params)
        payload = response.json()

        orders.extend(payload.get("orders", []))

        link_header = response.headers.get("Link", "")
        next_url = None

        if 'rel="next"' in link_header:
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip().strip("<>")

        url = next_url
        params = None

    return orders


def money(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def get_shipping_amount(order: dict) -> float:
    shipping_set = order.get("total_shipping_price_set") or {}
    shop_money = shipping_set.get("shop_money") or {}
    return money(shop_money.get("amount"))


def get_refund_amount(order: dict) -> float:
    total_refunds = 0.0

    for refund in order.get("refunds", []) or []:
        for transaction in refund.get("transactions", []) or []:
            if str(transaction.get("kind", "")).lower() == "refund":
                total_refunds += money(transaction.get("amount"))

    return total_refunds


def get_gross_sales(order: dict) -> float:
    gross_sales = 0.0

    for item in order.get("line_items", []) or []:
        quantity = money(item.get("quantity"))
        price = money(item.get("price"))
        gross_sales += quantity * price

    return gross_sales


def get_cogs(order: dict) -> float:
    """
    Shopify COGS only works if product cost is available in your data flow.
    If cost is not exposed in the order payload, keep this as 0 or enrich later
    from inventory/product cost data.
    """
    cogs = 0.0

    for item in order.get("line_items", []) or []:
        quantity = money(item.get("quantity"))
        cost = money(item.get("cost") or item.get("unit_cost"))
        cogs += quantity * cost

    return cogs


def normalize_shopify_orders(brand: str, orders: list[dict], year: int) -> list[dict]:
    rows = []

    for order in orders:
        created_at = order.get("created_at", "")
        month = created_at[5:7] if len(created_at) >= 7 else ""

        total_sales = money(order.get("total_price"))
        gross_sales = get_gross_sales(order)
        discounts = money(order.get("total_discounts"))
        returns = get_refund_amount(order)
        discounts_returns = discounts + returns
        shipping_charges = get_shipping_amount(order)

        net_sales = gross_sales - discounts - returns + shipping_charges

        cogs = get_cogs(order)
        gross_profit_1 = net_sales - cogs
        gross_margin_1 = gross_profit_1 / net_sales if net_sales else 0

        discounts_returns_pct = (
            discounts_returns / gross_sales if gross_sales else 0
        )

        rows.append({
            "brand": brand,
            "date": created_at[:10],
            "year": year,
            "month": month,
            "source": "Shopify",
            "channel": str(order.get("source_name", "Shopify")).title(),
            "financial_status": order.get("financial_status", ""),

            "total_sales": total_sales,
            "gross_sales": gross_sales,
            "discounts": discounts,
            "returns": returns,
            "discounts_returns": discounts_returns,
            "discounts_returns_pct": discounts_returns_pct,
            "shipping_charges": shipping_charges,
            "net_sales": net_sales,
            "cogs": cogs,
            "gross_profit_1": gross_profit_1,
            "gross_margin_1": gross_margin_1,
            "transactions": 1,
        })

    return rows
