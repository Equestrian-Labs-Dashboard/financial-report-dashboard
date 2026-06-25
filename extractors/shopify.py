import time
from datetime import datetime, timezone
import requests

API_VERSION = "2025-10"


def request_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    last_response = None

    for attempt in range(5):
        response = requests.request(method, url, timeout=60, **kwargs)
        last_response = response

        if response.status_code in [429, 500, 502, 503, 504]:
            wait_seconds = 2 ** attempt
            print(f"Shopify HTTP retry {attempt + 1}/5. Waiting {wait_seconds}s...")
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


def get_throttle_wait_seconds(errors: list[dict]) -> int:
    for error in errors:
        extensions = error.get("extensions") or {}

        if extensions.get("code") == "THROTTLED":
            cost = extensions.get("cost") or {}
            reset_at = cost.get("windowResetAt")

            if reset_at:
                try:
                    reset_dt = datetime.fromisoformat(reset_at.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    return max(int((reset_dt - now).total_seconds()) + 3, 8)
                except Exception:
                    return 15

            return 15

    return 0


def graphql_request(store: str, token: str, query: str, variables: dict | None = None) -> dict:
    url = f"https://{store}/admin/api/{API_VERSION}/graphql.json"

    for attempt in range(6):
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
        errors = data.get("errors") or []

        if errors:
            wait_seconds = get_throttle_wait_seconds(errors)

            if wait_seconds and attempt < 5:
                print(
                    f"Shopify GraphQL throttled. "
                    f"Waiting {wait_seconds}s before retry {attempt + 1}/5..."
                )
                time.sleep(wait_seconds)
                continue

            raise RuntimeError(f"Shopify GraphQL error: {errors}")

        return data

    raise RuntimeError("Shopify GraphQL failed after retries.")


def run_shopifyql(store: str, token: str, shopifyql: str) -> dict:
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
    columns = table.get("columns") or []
    rows = table.get("rows") or []

    column_names = []
    for index, column in enumerate(columns):
        column_names.append(
            column.get("name")
            or column.get("displayName")
            or f"col_{index}"
        )

    parsed = []

    for row in rows:
        if isinstance(row, dict):
            parsed.append(row)
            continue

        item = {}
        for index, value in enumerate(row):
            key = column_names[index] if index < len(column_names) else f"col_{index}"
            item[key] = value

        parsed.append(item)

    return parsed


def extract_month(value: str) -> str:
    value = str(value or "").strip()

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


def pick(row: dict, *names):
    normalized = {}

    for key, value in row.items():
        clean_key = str(key).lower().replace(" ", "_")
        normalized[clean_key] = value

    for name in names:
        clean_name = str(name).lower().replace(" ", "_")

        if name in row and row.get(name) is not None:
            return row.get(name)

        if clean_name in normalized and normalized.get(clean_name) is not None:
            return normalized.get(clean_name)

    return None


def get_shopify_analytics_monthly(brand: str, store: str, token: str, year: int) -> list[dict]:
    """
    Uses ShopifyQL monthly Analytics data.

    First attempt includes Shopify profit fields:
    - cost_of_goods_sold
    - gross_profit
    - gross_margin

    If the store/API does not expose those fields, it falls back to the accepted
    sales query and COGS remains 0 until Shopify exposes profit fields through
    ShopifyQL for that store.
    """
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    queries = [
        f"""
        FROM sales
        SHOW
          total_sales,
          gross_sales,
          discounts,
          returns,
          net_sales,
          shipping_charges,
          taxes,
          cost_of_goods_sold,
          gross_profit,
          gross_margin,
          orders
        TIMESERIES month
        SINCE {start_date}
        UNTIL {end_date}
        ORDER BY month ASC
        """,
        f"""
        FROM sales
        SHOW
          total_sales,
          gross_sales,
          discounts,
          returns,
          net_sales,
          shipping_charges,
          taxes,
          orders
        TIMESERIES month
        SINCE {start_date}
        UNTIL {end_date}
        ORDER BY month ASC
        """
    ]

    last_error = None

    for shopifyql in queries:
        try:
            response = run_shopifyql(store, token, shopifyql)
            rows = parse_shopifyql_table(response)

            if rows:
                return normalize_shopifyql_rows(brand, year, rows)

        except Exception as exc:
            last_error = exc
            print(f"{brand} {year}: ShopifyQL attempt failed: {exc}")

    raise RuntimeError(f"All ShopifyQL attempts failed. Last error: {last_error}")


def normalize_shopifyql_rows(brand: str, year: int, rows: list[dict]) -> list[dict]:
    normalized = []

    for row in rows:
        raw_month = str(pick(row, "month", "Month", "date", "Date", "day", "Day") or "")
        month = extract_month(raw_month)

        gross_sales = abs(money(pick(row, "gross_sales", "Gross sales")))
        discounts = abs(money(pick(row, "discounts", "Discounts")))
        returns = abs(money(pick(row, "returns", "Returns")))
        net_sales = money(pick(row, "net_sales", "Net sales"))
        shipping_charges = money(pick(row, "shipping_charges", "Shipping charges"))
        taxes = money(pick(row, "taxes", "Taxes"))
        total_sales = money(pick(row, "total_sales", "Total sales"))
        transactions = money(pick(row, "orders", "Orders"))

        cogs = abs(money(
            pick(
                row,
                "cost_of_goods_sold",
                "Cost of goods sold",
                "costs",
                "Costs",
                "cogs",
                "COGS"
            )
        ))

        discounts_returns = discounts + returns
        discounts_returns_pct = discounts_returns / gross_sales if gross_sales else 0

        analytics_gross_profit = pick(row, "gross_profit", "Gross profit")
        analytics_gross_margin = pick(row, "gross_margin", "Gross margin")

        if analytics_gross_profit is not None:
            gross_profit_1 = money(analytics_gross_profit)
        else:
            gross_profit_1 = net_sales - cogs

        if analytics_gross_margin is not None:
            gross_margin_raw = money(analytics_gross_margin)
            gross_margin_1 = gross_margin_raw / 100 if gross_margin_raw > 1 else gross_margin_raw
        else:
            gross_margin_1 = gross_profit_1 / net_sales if net_sales else 0

        normalized.append({
            "brand": brand,
            "date": f"{year}-{month}-01",
            "year": year,
            "month": month,
            "source": "Shopify Analytics",
            "channel": "Shopify",
            "financial_status": "analytics",
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
            "transactions": transactions,
            "sessions_reached_checkout": 0,
            "sessions_completed_checkout": 0,
            "checkout_abandonments": 0,
            "checkout_abandonment_rate": 0,
        })

    return normalized


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


def get_return_amount(order: dict) -> float:
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
        discounts = abs(money(order.get("total_discounts")))
        returns = get_return_amount(order)
        shipping_charges = get_shipping_amount(order)
        taxes = get_tax_amount(order)

        discounts_returns = discounts + returns
        discounts_returns_pct = discounts_returns / gross_sales if gross_sales else 0

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
            "sessions_reached_checkout": 0,
            "sessions_completed_checkout": 0,
            "checkout_abandonments": 0,
            "checkout_abandonment_rate": 0,
        })

    return rows





def get_checkout_funnel_monthly(brand: str, store: str, token: str, year: int) -> dict[str, dict[str, float]]:
    """
    Pulls checkout funnel metrics from ShopifyQL sessions.

    Shopify Analytics fields used:
    - sessions_that_reached_checkout
    - sessions_that_reached_and_completed_checkout

    Dashboard calculation:
    - checkout_abandonments = reached_checkout - completed_checkout
    - checkout_abandonment_rate = checkout_abandonments / reached_checkout
    """
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    monthly = {
        str(month).zfill(2): {
            "sessions_reached_checkout": 0,
            "sessions_completed_checkout": 0,
            "checkout_abandonments": 0,
            "checkout_abandonment_rate": 0,
        }
        for month in range(1, 13)
    }

    shopifyql = f"""
    FROM sessions
    SHOW
      sessions_that_reached_checkout,
      sessions_that_reached_and_completed_checkout
    TIMESERIES month
    SINCE {start_date}
    UNTIL {end_date}
    ORDER BY month ASC
    """

    try:
        response = run_shopifyql(store, token, shopifyql)
        rows = parse_shopifyql_table(response)

        for row in rows:
            raw_month = str(pick(row, "month", "Month", "date", "Date", "day", "Day") or "")
            month = extract_month(raw_month)

            reached = money(
                pick(
                    row,
                    "sessions_that_reached_checkout",
                    "Sessions that reached checkout",
                )
            )
            completed = money(
                pick(
                    row,
                    "sessions_that_reached_and_completed_checkout",
                    "Sessions that reached and completed checkout",
                )
            )

            abandoned = max(reached - completed, 0)
            rate = abandoned / reached if reached else 0

            if month in monthly:
                monthly[month] = {
                    "sessions_reached_checkout": reached,
                    "sessions_completed_checkout": completed,
                    "checkout_abandonments": abandoned,
                    "checkout_abandonment_rate": rate,
                }

        total_reached = sum(item["sessions_reached_checkout"] for item in monthly.values())
        total_completed = sum(item["sessions_completed_checkout"] for item in monthly.values())
        print(
            f"{brand} {year}: checkout funnel reached={int(total_reached)} "
            f"completed={int(total_completed)}"
        )

    except Exception as exc:
        print(f"{brand} {year}: Shopify sessions checkout funnel unavailable: {exc}")

    return monthly


def attach_checkout_funnel_metrics(rows: list[dict], checkout_funnel_by_month: dict[str, dict[str, float]]) -> list[dict]:
    for row in rows:
        month = str(row.get("month", "")).zfill(2)
        funnel = checkout_funnel_by_month.get(month, {})

        reached = float(funnel.get("sessions_reached_checkout") or 0)
        completed = float(funnel.get("sessions_completed_checkout") or 0)
        abandoned = max(reached - completed, 0)

        row["sessions_reached_checkout"] = reached
        row["sessions_completed_checkout"] = completed
        row["checkout_abandonments"] = abandoned
        row["checkout_abandonment_rate"] = abandoned / reached if reached else 0

    return rows


def get_shopify_rows(brand: str, store: str, token: str, year: int) -> list[dict]:
    rows = []

    try:
        print(f"Trying Shopify Analytics-style query for {brand} {year}...")
        rows = get_shopify_analytics_monthly(brand, store, token, year)
        print(f"{brand} {year}: Shopify Analytics rows: {len(rows)}")

    except Exception as exc:
        print(f"{brand} {year}: Shopify Analytics query unavailable: {exc}")
        print(f"{brand} {year}: Falling back to Orders API calculations.")

        orders = get_orders(brand=brand, store=store, token=token, year=year)
        print(f"{brand} Shopify orders: {len(orders)}")
        rows = normalize_shopify_orders(brand=brand, orders=orders, year=year)

    checkout_funnel_by_month = get_checkout_funnel_monthly(
        brand=brand,
        store=store,
        token=token,
        year=year,
    )

    return attach_checkout_funnel_metrics(rows, checkout_funnel_by_month)
