import time
import requests
import config

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


def get_orders(year: int) -> list[dict]:
    start_date = f"{year}-01-01T00:00:00Z"
    end_date = f"{year}-12-31T23:59:59Z"

    url = f"https://{config.SHOPIFY_STORE}/admin/api/{API_VERSION}/orders.json"

    headers = {
        "X-Shopify-Access-Token": config.SHOPIFY_TOKEN,
        "Content-Type": "application/json",
    }

    params = {
        "status": "any",
        "created_at_min": start_date,
        "created_at_max": end_date,
        "limit": 250,
        "fields": "id,created_at,total_price,subtotal_price,total_tax,total_discounts,source_name,financial_status,gateway,currency",
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


def normalize_orders(orders: list[dict], year: int) -> list[dict]:
    channel_map = {
        "web": "Online Store",
        "shopify": "Online Store",
        "pos": "POS",
        "draft_order": "Wholesale",
        "amazon": "Amazon",
        "facebook": "Facebook",
        "instagram": "Instagram",
        "tiktok": "TikTok",
    }

    rows = []

    for order in orders:
        created_at = order.get("created_at", "")
        raw_channel = str(order.get("source_name", "other")).lower()
        channel = channel_map.get(raw_channel, raw_channel.title())

        revenue = float(order.get("total_price") or 0)
        subtotal = float(order.get("subtotal_price") or 0)
        tax = float(order.get("total_tax") or 0)
        discounts = float(order.get("total_discounts") or 0)

        rows.append({
            "date": created_at[:10],
            "year": year,
            "month": created_at[5:7],
            "source": "Shopify",
            "channel": channel,
            "revenue": revenue,
            "subtotal": subtotal,
            "tax": tax,
            "discounts": discounts,
            "status": order.get("financial_status", ""),
            "transactions": 1,
        })

    return rows
