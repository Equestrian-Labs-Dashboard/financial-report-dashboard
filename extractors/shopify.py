import time
import requests

API_VERSION = "2025-10"


def request_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    last_response = None

    for attempt in range(5):
        response = requests.request(method, url, timeout=60, **kwargs)
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


def money(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def graphql_request(store: str, token: str, query: str, variables: dict | None = None) -> dict:
    url = f"https://{store}/admin/api/{API_VERSION}/graphql.json"

    response = request_with_retry(
        "POST",
        url,
        headers={
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "variables": variables or {},
        },
    )

    data = response.json()

    if data.get("errors"):
        raise RuntimeError(f"Shopify GraphQL error: {data['errors']}")

    return data


def run_shopifyql(store: str, token: str, shopifyql: str) -> dict:
    """
    Queries Shopify Analytics-style data through shopifyqlQuery.
    This should match Shopify Analytics closer than manually summing orders.
    """
    query = """
    query ShopifyAnalytics($query: String!) {
      shopifyqlQuery(query: $query) {
        tableData {
          columns {
            name
            dataType
            displayName
          }
          rows
        }
        parseErrors
      }
    }
    """

    return graphql_request(
        store=store,
        token=token,
        query=query,
        variables={"query": shopifyql},
    )


def parse_shopifyql_table(response: dict) -> list[dict]:
    payload = response.get("data", {}).get("shopifyqlQuery", {})

    parse_errors = payload.get("parseErrors")
    if parse_errors:
        raise RuntimeError(f"ShopifyQL parse errors: {parse_errors}")

    table = payload.get("tableData") or {}
    rows = table.get("rows") or []

    parsed = []

    for row in rows:
        parsed.append(row)

    return parsed

def get_shopify_analytics_monthly(brand: str, store: str, token: str, year: int) -> list[dict]:
    """
    Best-effort Shopify Analytics-style monthly report.

    This is designed to match Shopify Analytics closer than Orders API because
    Shopify's analytics reports apply reporting logic to returns, discounts,
    taxes, shipping, and sales reversals.
    """
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    shopifyql = f"""
    FROM sales
    SHOW
      total_sales,
      gross_sales,
      discounts,
      returns,
      net_sales,
      shipping_charges,
      taxes
    GROUP BY month
    SINCE {start_date}
    UNTIL {end_date}
    ORDER BY month ASC
    """

    response = run_shopifyql(store, token, shopifyql)
    rows = parse_shopifyql_table(response)

    normalized = []

    for row in rows:
        raw_month = str(row.get("month") or row.get("Month") or "")
        month = extract_month(raw_month)

        gross_sales = money(row.get("gross_sales") or row.get("Gross sales"))
        discounts = abs(money(row.get("discounts") or row.get("Discounts")))
        returns = abs(money(row.get("returns") or row.get("Returns")))
        discounts_returns = discounts + returns
        net_sales = money(row.get("net_sales") or row.get("Net sales"))
        shipping_charges = money(row.get("shipping_charges") or row.get("Shipping charges"))
        taxes = money(row.get("taxes") or row.get("Taxes"))
        total_sales = money(row.get("total_sales") or row.get("Total sales"))

        cogs = 0.0
        gross_profit_1 = net_sales - cogs
        gross_margin_1 = gross_profit_1 / net_sales if net_sales else 0
        discounts_returns_pct = discounts_returns / gross_sales if gross_sales else 0

        normalized.append({
            "brand": brand,
            "year": year,
            "month": month,
            "source": "Shopify Analytics",
            "total_sales": total_sales,
            "gross_sales": gross_sales,
            "discounts": discounts,
            "returns": returns,
            "discounts_returns": discounts_returns,
            "discounts_returns_pct": discounts_returns_pct,
            "shipping_charges": shipping_charges,
            "taxes": taxes,
            "net_sales": net_sales,
            "cogs": cogs,
            "gross_profit_1": gross_profit_1,
            "gross_margin_1": gross_margin_1,
            "transactions": 0,
        })

    return normalized


def extract_month(value: str) -> str:
    value = str(value)

    if len(value) >= 7 and value[4] == "-":
        return value[5:7]

    months = {
        "jan": "01",
        "feb": "02",
        "mar": "03",
        "apr": "04",
        "may": "05",
        "jun": "06",
        "jul": "07",
        "aug": "08",
        "sep": "09",
        "oct": "10",
        "nov": "11",
        "dec": "12",
    }

    lower = value.lower()[:3]
    return months.get(lower, value.zfill(2))


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
    "id,created_at,total_price,current_total_price,"
    "subtotal_price,current_subtotal_price,total_tax,current_total_tax,"
    "total_discounts,current_total_discounts,total_shipping_price_set,"
    "shipping_lines,source_name,financial_status,line_items,refunds,"
    "currency,cancelled_at,test"
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


def get_shipping_amount(order: dict) -> float:
    shipping_total = 0.0

    shipping_lines = order.get("shipping_lines") or []

    if shipping_lines:
        for shipping_line in shipping_lines:
            discounted_set = shipping_line.get("discounted_price_set") or {}
            shop_money = discounted_set.get("shop_money") or {}

            if shop_money.get("amount") is not None:
                shipping_total += money(shop_money.get("amount"))
            else:
                shipping_total += money(shipping_line.get("price"))
    else:
        shipping_set = order.get("total_shipping_price_set") or {}
        shop_money = shipping_set.get("shop_money") or {}
        shipping_total = money(shop_money.get("amount"))

    shipping_refunds = get_shipping_refund_amount(order)

    return max(shipping_total - shipping_refunds, 0)


def get_shipping_refund_amount(order: dict) -> float:
    shipping_refunds = 0.0

    for refund in order.get("refunds", []) or []:
        for adjustment in refund.get("order_adjustments", []) or []:
            kind = str(adjustment.get("kind", "")).lower()

            if kind == "shipping_refund":
                amount_set = adjustment.get("amount_set") or {}
                shop_money = amount_set.get("shop_money") or {}

                if shop_money.get("amount") is not None:
                    shipping_refunds += abs(money(shop_money.get("amount")))
                else:
                    shipping_refunds += abs(money(adjustment.get("amount")))

    return shipping_refunds


def get_return_amount(order: dict) -> float:
    """
    Shopify Analytics Returns should be product returns, not full refund transactions.
    refund.transactions.amount can include product + tax + shipping, so it overstates returns.
    """
    total_returns = 0.0

    for refund in order.get("refunds", []) or []:
        for refund_line_item in refund.get("refund_line_items", []) or []:
            subtotal_set = refund_line_item.get("subtotal_set") or {}
            shop_money = subtotal_set.get("shop_money") or {}

            if shop_money.get("amount") is not None:
                total_returns += abs(money(shop_money.get("amount")))
            else:
                total_returns += abs(money(refund_line_item.get("subtotal")))

    return total_returns


def get_tax_amount(order: dict) -> float:
    """
    current_total_tax better reflects refunds/order edits when available.
    """
    if order.get("current_total_tax") is not None:
        return money(order.get("current_total_tax"))

    return money(order.get("total_tax"))


def get_gross_sales(order: dict) -> float:
    gross_sales = 0.0

    for item in order.get("line_items", []) or []:
        quantity = money(item.get("quantity"))
        price = money(item.get("price"))
        gross_sales += quantity * price

    return gross_sales


def get_cogs(order: dict) -> float:
    cogs = 0.0

    for item in order.get("line_items", []) or []:
        quantity = money(item.get("quantity"))
        cost = money(item.get("cost") or item.get("unit_cost"))
        cogs += quantity * cost

    return cogs


def normalize_shopify_orders(brand: str, orders: list[dict], year: int) -> list[dict]:
    rows = []

    for order in orders:
        if order.get("test") is True:
            continue

        created_at = order.get("created_at", "")
        month = created_at[5:7] if len(created_at) >= 7 else ""

        gross_sales = get_gross_sales(order)

        # Shopify Analytics-style fields
        discounts = abs(money(order.get("total_discounts")))
        returns = get_return_amount(order)
        shipping_charges = get_shipping_amount(order)
        taxes = get_tax_amount(order)

        discounts_returns = discounts + returns
        discounts_returns_pct = discounts_returns / gross_sales if gross_sales else 0

        # Shopify-style definitions:
        # Net sales = Gross sales - Discounts - Returns
        # Total sales = Net sales + Shipping charges + Taxes
        net_sales = gross_sales - discounts - returns
        total_sales = net_sales + shipping_charges + taxes

        cogs = get_cogs(order)
        gross_profit_1 = net_sales - cogs
        gross_margin_1 = gross_profit_1 / net_sales if net_sales else 0

        rows.append({
            "brand": brand,
            "date": created_at[:10],
            "year": year,
            "month": month,
            "source": "Shopify Orders API",
            "channel": str(order.get("source_name", "Shopify")).title(),
            "financial_status": order.get("financial_status", ""),

            "total_sales": total_sales,
            "gross_sales": gross_sales,
            "discounts": discounts,
            "returns": returns,
            "discounts_returns": discounts_returns,
            "discounts_returns_pct": discounts_returns_pct,
            "shipping_charges": shipping_charges,
            "taxes": taxes,
            "net_sales": net_sales,
            "cogs": cogs,
            "gross_profit_1": gross_profit_1,
            "gross_margin_1": gross_margin_1,
            "transactions": 1,
        })

    return rows

def get_shopify_rows(brand: str, store: str, token: str, year: int) -> list[dict]:
    """
    Preferred: Shopify Analytics / ShopifyQL-style metrics.
    Fallback: Orders API calculations.
    """
    try:
        print(f"Trying Shopify Analytics-style query for {brand} {year}...")
        rows = get_shopify_analytics_monthly(brand, store, token, year)

        if rows:
            print(f"{brand} {year}: Shopify Analytics rows: {len(rows)}")
            return rows

        print(f"{brand} {year}: Shopify Analytics returned no rows. Falling back to Orders API.")

    except Exception as exc:
        print(f"{brand} {year}: Shopify Analytics query unavailable: {exc}")
        print(f"{brand} {year}: Falling back to Orders API calculations.")

    orders = get_orders(brand=brand, store=store, token=token, year=year)
    print(f"{brand} Shopify orders: {len(orders)}")

    return normalize_shopify_orders(brand=brand, orders=orders, year=year)
