import time
from datetime import datetime, timezone
import requests

API_VERSION = "2025-10"

# Wellington is a store/POS split inside Corro, not a warehouse split and not Cavali.
WELLINGTON_PARENT_BRAND = "Corro"

# Keep this filter strict so online orders fulfilled from Wellington warehouse
# do not appear as Wellington Store sales.
POS_SOURCE_NAMES = {
    "pos",
    "shopify_pos",
    "shopify pos",
    "point of sale",
    "point_of_sale",
}

ONLINE_SOURCE_NAMES = {
    "web",
    "online_store",
    "online store",
    "shopify_draft_order",
    "draft order",
    "draft_orders",
    "marketplace connect",
}



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

        has_shopify_gross_profit_1 = analytics_gross_profit is not None
        has_shopify_gross_margin_1 = analytics_gross_margin is not None

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
            "shopify_gross_profit_1_source": 1 if has_shopify_gross_profit_1 else 0,
            "shopify_gross_margin_1_source": 1 if has_shopify_gross_margin_1 else 0,
            "transactions": transactions,
            "orders": transactions,
            "units_sold": 0,
            "customers": 0,
            "new_customers": 0,
            "returning_customers": 0,
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
            "shipping_lines,source_name,app_id,financial_status,line_items,refunds,"
            "location_id,fulfillments,customer,email,currency,cancelled_at,test,"
            "tags,note_attributes"
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



def chunked(values: list, size: int) -> list[list]:
    return [values[index:index + size] for index in range(0, len(values), size)]


def get_variant_ids_from_orders(orders: list[dict]) -> list[str]:
    ids = set()

    for order in orders:
        for item in order.get("line_items", []) or []:
            variant_id = item.get("variant_id")

            if variant_id:
                ids.add(str(variant_id))

    return sorted(ids)


def get_variant_unit_costs(store: str, token: str, orders: list[dict]) -> dict[str, float]:
    """
    REST Orders do not include product cost. For Wellington/POS rows we enrich
    COGS from ProductVariant.inventoryItem.unitCost through GraphQL.
    """
    variant_ids = get_variant_ids_from_orders(orders)

    if not variant_ids:
        return {}

    query = """
    query VariantCosts($ids: [ID!]!) {
      nodes(ids: $ids) {
        ... on ProductVariant {
          id
          legacyResourceId
          inventoryItem {
            unitCost {
              amount
            }
          }
        }
      }
    }
    """

    costs = {}

    for batch in chunked(variant_ids, 100):
        gids = [f"gid://shopify/ProductVariant/{variant_id}" for variant_id in batch]

        try:
            data = graphql_request(
                store=store,
                token=token,
                query=query,
                variables={"ids": gids},
            )
        except Exception as exc:
            print(f"Shopify variant COGS lookup failed for {len(batch)} variants: {exc}")
            continue

        for node in (data.get("data", {}) or {}).get("nodes", []) or []:
            if not node:
                continue

            legacy_id = str(node.get("legacyResourceId") or "")
            inventory_item = node.get("inventoryItem") or {}
            unit_cost = inventory_item.get("unitCost") or {}
            amount = money(unit_cost.get("amount"))

            if legacy_id:
                costs[legacy_id] = amount

    return costs


def is_pos_order(order: dict) -> bool:
    source_name = str(order.get("source_name") or "").strip().lower()

    if source_name in POS_SOURCE_NAMES:
        return True

    return "pos" in source_name or "point of sale" in source_name


def is_online_order(order: dict) -> bool:
    source_name = str(order.get("source_name") or "").strip().lower()

    if source_name in ONLINE_SOURCE_NAMES:
        return True

    return "online" in source_name or source_name == "web"


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


def get_units_sold(order: dict) -> float:
    units = 0.0

    for item in order.get("line_items", []) or []:
        units += money(item.get("quantity"))

    return units


def get_customer_id(order: dict) -> str:
    customer = order.get("customer") or {}
    customer_id = customer.get("id")

    if customer_id:
        return str(customer_id)

    email = customer.get("email") or order.get("email")
    return str(email or "")



def get_customer_orders_count(order: dict) -> float:
    customer = order.get("customer") or {}
    return money(customer.get("orders_count"))


def get_order_activity_monthly(orders: list[dict]) -> dict[str, dict[str, float]]:
    """
    Builds monthly operational KPIs from Orders API:
    - orders
    - units sold
    - unique customers
    - new customers
    - returning customers

    New/returning is calculated within the extracted year:
    first month where the customer appears = new;
    later months where the same customer appears = returning.
    """
    monthly = {
        str(month).zfill(2): {
            "transactions": 0,
            "units_sold": 0,
            "customers": 0,
            "new_customers": 0,
            "returning_customers": 0,
            "_customers": set(),
            "_new_customers": set(),
            "_returning_customers": set(),
        }
        for month in range(1, 13)
    }

    first_seen_month_by_customer = {}

    sorted_orders = sorted(
        [order for order in orders if order.get("test") is not True],
        key=lambda order: order.get("created_at", "")
    )

    for order in sorted_orders:
        created_at = order.get("created_at", "")
        month = created_at[5:7] if len(created_at) >= 7 else ""

        if month not in monthly:
            continue

        customer_id = get_customer_id(order)
        units_sold = get_units_sold(order)

        monthly[month]["transactions"] += 1
        monthly[month]["units_sold"] += units_sold

        if customer_id:
            monthly[month]["_customers"].add(customer_id)

            if customer_id not in first_seen_month_by_customer:
                first_seen_month_by_customer[customer_id] = month
                monthly[month]["_new_customers"].add(customer_id)
            else:
                monthly[month]["_returning_customers"].add(customer_id)

    for month, data in monthly.items():
        data["customers"] = len(data["_customers"])
        data["new_customers"] = len(data["_new_customers"])
        data["returning_customers"] = len(data["_returning_customers"])

        data.pop("_customers", None)
        data.pop("_new_customers", None)
        data.pop("_returning_customers", None)

    return monthly


def attach_order_activity_metrics(rows: list[dict], orders: list[dict]) -> list[dict]:
    activity_by_month = get_order_activity_monthly(orders)

    for row in rows:
        month = str(row.get("month", "")).zfill(2)
        activity = activity_by_month.get(month, {})

        row["transactions"] = float(activity.get("transactions") or row.get("transactions") or 0)
        row["orders"] = float(activity.get("transactions") or row.get("transactions") or 0)
        row["units_sold"] = float(activity.get("units_sold") or 0)
        row["customers"] = float(activity.get("customers") or 0)
        row["new_customers"] = float(activity.get("new_customers") or 0)
        row["returning_customers"] = float(activity.get("returning_customers") or 0)

    return rows



def attach_order_cost_metrics(
    rows: list[dict],
    orders: list[dict],
    variant_unit_costs: dict[str, float] | None = None,
) -> list[dict]:
    """
    Enriches ShopifyQL monthly rows with COGS from Orders API + ProductVariant.inventoryItem.unitCost.
    """
    variant_unit_costs = variant_unit_costs or {}
    monthly_cogs = {str(month).zfill(2): 0.0 for month in range(1, 13)}

    for order in orders:
        if order.get("test") is True:
            continue

        created_at = order.get("created_at", "")
        month = created_at[5:7] if len(created_at) >= 7 else ""

        if month in monthly_cogs:
            monthly_cogs[month] += get_cogs(order, variant_unit_costs=variant_unit_costs)

    total_cogs = sum(monthly_cogs.values())
    print(f"Order API COGS enrichment total={round(total_cogs, 2)}")

    for row in rows:
        month = str(row.get("month", "")).zfill(2)
        enriched_cogs = monthly_cogs.get(month, 0.0)

        if enriched_cogs > 0 and money(row.get("cogs")) <= 0:
            row["cogs"] = enriched_cogs

            # IMPORTANT: if ShopifyQL returned Gross Profit / Gross Margin, keep
            # those Shopify values. Do not replace GM1 with a local calculation.
            if not money(row.get("shopify_gross_profit_1_source")):
                row["gross_profit_1"] = money(row.get("net_sales")) - enriched_cogs

            if not money(row.get("shopify_gross_margin_1_source")):
                row["gross_margin_1"] = (
                    money(row.get("gross_profit_1")) / money(row.get("net_sales"))
                    if money(row.get("net_sales"))
                    else 0
                )

    return rows


def get_cogs(order: dict, variant_unit_costs: dict[str, float] | None = None) -> float:
    variant_unit_costs = variant_unit_costs or {}
    raw_cogs = 0.0

    for item in order.get("line_items", []) or []:
        quantity = money(item.get("quantity"))
        variant_id = str(item.get("variant_id") or "")

        cost = money(
            item.get("cost")
            or item.get("unit_cost")
            or variant_unit_costs.get(variant_id)
        )

        raw_cogs += quantity * cost

    # Match the commission/report logic: reduce COGS proportionally when returns
    # reduce net sales, so refunded items do not keep full COGS in margin.
    gross_sales = get_gross_sales(order)
    discounts = abs(money(order.get("total_discounts")))
    returns = get_return_amount(order)
    net_before_returns = max(gross_sales - discounts, 0)
    net_after_returns = max(net_before_returns - returns, 0)

    if net_before_returns > 0:
        cogs_factor = max(0, min(1, net_after_returns / net_before_returns))
    else:
        cogs_factor = 0

    return raw_cogs * cogs_factor


def normalize_shopify_orders(brand: str, orders: list[dict], year: int, variant_unit_costs: dict[str, float] | None = None) -> list[dict]:
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

        units_sold = get_units_sold(order)
        customer_id = get_customer_id(order)

        cogs = get_cogs(order, variant_unit_costs=variant_unit_costs)
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
            "shopify_gross_profit_1_source": 0,
            "shopify_gross_margin_1_source": 0,
            "transactions": 1,
            "orders": 1,
            "units_sold": units_sold,
            "customer_id": customer_id,
            "customers": 1 if customer_id else 0,
            "new_customers": 0,
            "returning_customers": 0,
            "view_type": "brand",
            "parent_brand": brand,
            "location_filter": "All Locations",
            "location_id": "",
            "location_name": "",
            "sessions_reached_checkout": 0,
            "sessions_completed_checkout": 0,
            "checkout_abandonments": 0,
            "checkout_abandonment_rate": 0,
        })

    return rows






def gql_money(value) -> float:
    if value is None:
        return 0.0

    if isinstance(value, (int, float, str)):
        return money(value)

    if isinstance(value, dict):
        if "amount" in value:
            return money(value.get("amount"))

        shop_money = value.get("shopMoney") or value.get("shop_money") or {}
        if isinstance(shop_money, dict) and "amount" in shop_money:
            return money(shop_money.get("amount"))

    return 0.0


def gql_edges_nodes(connection: dict | None) -> list[dict]:
    if not connection:
        return []

    if isinstance(connection.get("nodes"), list):
        return connection.get("nodes") or []

    return [
        (edge or {}).get("node")
        for edge in (connection.get("edges") or [])
        if (edge or {}).get("node")
    ]


def get_refund_subtotal_by_line_item_id(order: dict) -> dict[str, float]:
    refund_map = {}

    for refund in order.get("refunds", []) or []:
        for refund_line in gql_edges_nodes(refund.get("refundLineItems")):
            line_item = refund_line.get("lineItem") or {}
            line_id = line_item.get("id")
            if not line_id:
                continue

            refund_map[line_id] = refund_map.get(line_id, 0.0) + abs(
                gql_money(refund_line.get("subtotalSet"))
            )

    return refund_map


def is_wellington_name(name: str, location_name: str) -> bool:
    clean = str(name or "").lower()
    target = str(location_name or "").lower()
    return "wellington" in clean or (target and target in clean)


def graphql_order_has_wellington_evidence(order: dict, location_name: str) -> bool:
    physical_location = order.get("physicalLocation") or {}
    if is_wellington_name(physical_location.get("name"), location_name):
        return True

    for fulfillment in order.get("fulfillments", []) or []:
        location = fulfillment.get("location") or {}
        if is_wellington_name(location.get("name"), location_name):
            return True

    return False


def graphql_order_source_name(order: dict) -> str:
    source_name = str(order.get("sourceName") or "").strip().lower()
    app = order.get("app") or {}
    app_name = str(app.get("name") or "").strip().lower()
    return f"{source_name} {app_name}".strip()


def graphql_order_is_online(order: dict) -> bool:
    source = graphql_order_source_name(order)
    return any(name in source for name in ONLINE_SOURCE_NAMES) or "online" in source or source == "web"


def graphql_order_is_pos(order: dict) -> bool:
    source = graphql_order_source_name(order)
    return any(name in source for name in POS_SOURCE_NAMES) or "pos" in source or "point of sale" in source


def graphql_shipping_amount(order: dict) -> float:
    return gql_money(order.get("totalShippingPriceSet"))


def fetch_wellington_graphql_orders(store: str, token: str, year: int, location_id: str) -> list[dict]:
    query = """
    query WellingtonOrders($first: Int!, $after: String, $query: String!) {
      orders(first: $first, after: $after, query: $query, sortKey: CREATED_AT) {
        nodes {
          id
          name
          createdAt
          tags
          sourceName
          app { name }
          physicalLocation { name }
          cancelledAt
          test
          totalShippingPriceSet { shopMoney { amount } }
          currentTotalTaxSet { shopMoney { amount } }
          lineItems(first: 100) {
            nodes {
              id
              title
              quantity
              originalTotalSet { shopMoney { amount } }
              totalDiscountSet { shopMoney { amount } }
              discountedTotalSet { shopMoney { amount } }
              variant {
                id
                inventoryItem {
                  unitCost { amount }
                }
              }
            }
          }
          refunds(first: 100) {
            refundLineItems(first: 100) {
              nodes {
                subtotalSet { shopMoney { amount } }
                lineItem { id }
              }
            }
          }
          fulfillments(first: 20) {
            location { name }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    """

    search_query = (
        f"location_id:{location_id} status:any "
        f"created_at:>={year}-01-01 created_at:<={year}-12-31"
    )

    orders = []
    after = None

    while True:
        data = graphql_request(
            store=store,
            token=token,
            query=query,
            variables={"first": 50, "after": after, "query": search_query},
        )

        connection = (data.get("data") or {}).get("orders") or {}
        orders.extend(connection.get("nodes") or [])

        page_info = connection.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break

        after = page_info.get("endCursor")

    return orders


def graphql_order_to_wellington_row(order: dict, parent_brand: str, year: int, location_id: str, location_name: str) -> dict:
    month = str(order.get("createdAt") or "")[5:7]
    refund_map = get_refund_subtotal_by_line_item_id(order)

    gross_sales = 0.0
    discounts = 0.0
    returns = 0.0
    net_sales = 0.0
    cogs = 0.0
    units = 0.0

    for item in gql_edges_nodes(order.get("lineItems")):
        quantity = money(item.get("quantity"))
        gross = gql_money(item.get("originalTotalSet"))
        discount = abs(gql_money(item.get("totalDiscountSet")))
        net_before_returns = gql_money(item.get("discountedTotalSet"))
        line_return = abs(refund_map.get(item.get("id"), 0.0))
        net = max(net_before_returns - line_return, 0.0)

        variant = item.get("variant") or {}
        inventory_item = variant.get("inventoryItem") or {}
        unit_cost = gql_money(inventory_item.get("unitCost") or {})
        raw_cogs = unit_cost * max(quantity, 0)

        cogs_factor = net / net_before_returns if net_before_returns > 0 else 0
        cogs_factor = max(0, min(1, cogs_factor))

        gross_sales += gross
        discounts += discount
        returns += line_return
        net_sales += net
        cogs += raw_cogs * cogs_factor
        units += quantity

    taxes = gql_money(order.get("currentTotalTaxSet"))
    shipping = 0.0
    total_sales = net_sales + taxes
    discounts_returns = discounts + returns
    gross_profit_1 = net_sales - cogs

    return {
        "brand": parent_brand,
        "year": int(year),
        "month": month,
        "channel": "Point of Sale / Wellington",
        "view_type": "location",
        "split_type": "wellington",
        "split_filter": "Wellington",
        "parent_brand": parent_brand,
        "location_filter": "Wellington",
        "location_id": str(location_id),
        "location_name": location_name,
        "total_sales": total_sales,
        "gross_sales": gross_sales,
        "discounts": discounts,
        "returns": returns,
        "discounts_returns": discounts_returns,
        "discounts_returns_pct": discounts_returns / gross_sales if gross_sales else 0,
        "shipping_charges": shipping,
        "taxes": taxes,
        "net_sales": net_sales,
        "cogs": cogs,
        "gross_profit_1": gross_profit_1,
        "gross_margin_1": gross_profit_1 / net_sales if net_sales else 0,
        "shopify_gross_profit_1_source": 0,
        "shopify_gross_margin_1_source": 0,
        "transactions": 1,
        "orders": 1,
        "units_sold": units,
        "customers": 0,
        "new_customers": 0,
        "returning_customers": 0,
        "sessions_reached_checkout": 0,
        "sessions_completed_checkout": 0,
        "checkout_abandonments": 0,
        "checkout_abandonment_rate": 0,
    }


def order_matches_location(order: dict, location_id: str) -> bool:
    target = str(location_id)

    order_location_id = order.get("location_id")
    if order_location_id is not None and str(order_location_id) == target:
        return True

    for fulfillment in order.get("fulfillments", []) or []:
        fulfillment_location_id = fulfillment.get("location_id")
        if fulfillment_location_id is not None and str(fulfillment_location_id) == target:
            return True

    for item in order.get("line_items", []) or []:
        origin_location = item.get("origin_location") or {}
        origin_location_id = origin_location.get("id")
        if origin_location_id is not None and str(origin_location_id) == target:
            return True

    return False


def order_matches_wellington_store(order: dict, location_id: str) -> bool:
    """
    Wellington Store is not the same thing as Wellington warehouse fulfillment.

    The earlier location-only filter captured online orders shipped from the
    Wellington warehouse, which inflated Total Sales and showed Shipping.
    This stricter filter keeps only orders that:
    - belong to the Wellington location,
    - come from Shopify POS / Point of Sale,
    - do not have online/web source_name,
    - have zero collected shipping.
    """
    if not order_matches_location(order, location_id=location_id):
        return False

    if is_online_order(order):
        return False

    if not is_pos_order(order):
        return False

    if get_shipping_amount(order) > 0.01:
        return False

    return True



def split_shopify_tags(value) -> list[str]:
    if isinstance(value, list):
        raw_values = value
    else:
        raw_values = str(value or "").replace(";", ",").split(",")

    return [str(tag or "").strip().lower() for tag in raw_values if str(tag or "").strip()]


def has_exact_or_word_tag(tags, target: str) -> bool:
    target = str(target or "").strip().lower()
    if not target:
        return False

    tag_list = split_shopify_tags(tags)
    if target in tag_list:
        return True

    # Fallback for malformed tag strings from Shopify exports.
    return any(target in tag for tag in tag_list)


def get_customer_tags(order: dict) -> str:
    customer = order.get("customer") or {}
    return str(customer.get("tags") or "")


def order_matches_concierge(order: dict) -> bool:
    """
    Concierge split follows the existing commission pipeline's source-of-truth:
    the order qualifies when Concierge context is present in Shopify order tags
    or customer tags. We intentionally ignore the 2-letter rep initials (DG, LH,
    SS, JS, JW, etc.); those were only for rep-level commission reports, not for
    the financial split.

    Accepted context tags/words:
    - concierge
    - commissioneligible (keeps compatibility with the commission pipeline)
    - source_name containing concierge, if a store/app sends that instead of tags
    """
    source_name = str(order.get("source_name") or "").lower().strip()
    order_tags = order.get("tags") or ""
    customer_tags = get_customer_tags(order)

    return (
        "concierge" in source_name
        or has_exact_or_word_tag(order_tags, "concierge")
        or has_exact_or_word_tag(customer_tags, "concierge")
        or has_exact_or_word_tag(order_tags, "commissioneligible")
        or has_exact_or_word_tag(customer_tags, "commissioneligible")
    )


def get_shopify_concierge_rows(parent_brand: str, store: str, token: str, year: int) -> list[dict]:
    """
    Corro-only Concierge split. This uses the same base order calculations as
    the brand rows, but only includes orders tagged/source_name with Concierge.
    """
    if str(parent_brand).lower() != "corro":
        print(f"{parent_brand} {year}: Concierge skipped. Concierge is Corro only.")
        return []

    orders = get_orders(brand=parent_brand, store=store, token=token, year=year)
    concierge_orders = [order for order in orders if order_matches_concierge(order)]
    variant_unit_costs = get_variant_unit_costs(store=store, token=token, orders=concierge_orders)

    rows = normalize_shopify_orders(
        brand=parent_brand,
        orders=concierge_orders,
        year=year,
        variant_unit_costs=variant_unit_costs,
    )

    for row in rows:
        row["view_type"] = "location"
        row["split_type"] = "concierge"
        row["split_filter"] = "Concierge"
        row["parent_brand"] = parent_brand
        row["location_filter"] = "Concierge"
        row["location_id"] = ""
        row["location_name"] = "Concierge"
        row["channel"] = "Concierge"

    total_sales = sum(money(row.get("total_sales")) for row in rows)
    total_cogs = sum(money(row.get("cogs")) for row in rows)
    print(f"{parent_brand} {year}: Concierge orders matched={len(concierge_orders)} sales={round(total_sales, 2)} cogs={round(total_cogs, 2)}")

    return rows


def get_shopify_location_rows(
    view_name: str,
    parent_brand: str,
    store: str,
    token: str,
    year: int,
    location_id: str,
    location_name: str,
) -> list[dict]:
    """
    Builds the Wellington Store view.

    Wellington is Corro-only. It is NOT Cavali and NOT a warehouse-only split.
    Uses GraphQL line-level data so COGS can come from variant.inventoryItem.unitCost.
    """
    if str(parent_brand).lower() != WELLINGTON_PARENT_BRAND.lower():
        print(f"{parent_brand} {year}: {view_name} skipped. Wellington is Corro only.")
        return []

    try:
        gql_orders = fetch_wellington_graphql_orders(
            store=store,
            token=token,
            year=year,
            location_id=str(location_id),
        )

        location_only_count = len(gql_orders)

        matched_orders = [
            order for order in gql_orders
            if not order.get("test")
            and graphql_order_has_wellington_evidence(order, location_name=location_name)
            and graphql_order_is_pos(order)
            and not graphql_order_is_online(order)
            and graphql_shipping_amount(order) <= 0.01
        ]

        rows = [
            graphql_order_to_wellington_row(
                order,
                parent_brand=parent_brand,
                year=year,
                location_id=str(location_id),
                location_name=str(location_name),
            )
            for order in matched_orders
        ]

        total_cogs = sum(money(row.get("cogs")) for row in rows)
        total_sales = sum(money(row.get("total_sales")) for row in rows)

        print(
            f"{parent_brand} {year}: {view_name} GraphQL POS orders matched={len(matched_orders)} "
            f"(location-only before POS/shipping filter={location_only_count}) "
            f"sales={round(total_sales, 2)} cogs={round(total_cogs, 2)}"
        )

        return rows

    except Exception as exc:
        print(f"{parent_brand} {year}: Wellington GraphQL extraction failed, using REST fallback: {exc}")

    orders = get_orders(brand=parent_brand, store=store, token=token, year=year)

    location_only_count = sum(
        1 for order in orders
        if order_matches_location(order, location_id=location_id)
    )

    location_orders = [
        order for order in orders
        if order_matches_wellington_store(order, location_id=location_id)
    ]

    variant_unit_costs = get_variant_unit_costs(store=store, token=token, orders=location_orders)

    rows = normalize_shopify_orders(
        brand=parent_brand,
        orders=location_orders,
        year=year,
        variant_unit_costs=variant_unit_costs,
    )

    for row in rows:
        row["view_type"] = "location"
        row["split_type"] = "wellington"
        row["split_filter"] = view_name
        row["parent_brand"] = parent_brand
        row["location_filter"] = view_name
        row["location_id"] = str(location_id)
        row["location_name"] = location_name
        row["channel"] = "Point of Sale / Wellington"
        row["shipping_charges"] = 0.0
        row["shipping_cost"] = 0.0
        row["total_sales"] = row["net_sales"] + row["taxes"]

    total_cogs = sum(money(row.get("cogs")) for row in rows)

    print(
        f"{parent_brand} {year}: {view_name} REST fallback POS orders matched={len(location_orders)} "
        f"(location-only before POS/shipping filter={location_only_count}) "
        f"cogs={round(total_cogs, 2)} location_id={location_id}"
    )

    return rows


def get_checkout_funnel_monthly(brand: str, store: str, token: str, year: int) -> dict[str, dict[str, float]]:
    """
    Pulls checkout funnel metrics from ShopifyQL sessions.

    Preferred ShopifyQL formula:
    - Reached Checkout: sessions_that_reached_checkout
    - Completed Checkout: sessions_that_reached_and_completed_checkout
    - Checkout Abandonments: reached - completed
    - Checkout Abandonment Rate: (reached - completed) / reached

    The first query uses GROUP BY month because that is what Shopify Analytics
    accepts for this sessions funnel in some stores. The second query keeps
    TIMESERIES month as a backup.
    """
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    monthly = {
        str(month).zfill(2): {
            "sessions_reached_checkout": 0,
            "sessions_completed_checkout": 0,
            "checkout_abandonments": 0,
            "checkout_abandonment_rate": 0,
            "checkout_funnel_source": "none",
        }
        for month in range(1, 13)
    }

    shopifyql_attempts = [
        f"""
        FROM sessions
        SHOW
          sessions_that_reached_checkout,
          sessions_that_reached_and_completed_checkout
        GROUP BY month
        SINCE {start_date}
        UNTIL {end_date}
        ORDER BY month ASC
        """,
        f"""
        FROM sessions
        SHOW
          sessions_that_reached_checkout,
          sessions_that_reached_and_completed_checkout
        TIMESERIES month
        SINCE {start_date}
        UNTIL {end_date}
        ORDER BY month ASC
        """,
    ]

    last_error = None

    for shopifyql in shopifyql_attempts:
        try:
            response = run_shopifyql(store, token, shopifyql)
            rows = parse_shopifyql_table(response)

            for row in rows:
                raw_month = str(
                    pick(
                        row,
                        "month",
                        "Month",
                        "date",
                        "Date",
                        "day",
                        "Day",
                        "group",
                        "Group",
                    )
                    or ""
                )
                month = extract_month(raw_month)

                reached = money(
                    pick(
                        row,
                        "sessions_that_reached_checkout",
                        "Sessions that reached checkout",
                        "Reached checkout",
                    )
                )
                completed = money(
                    pick(
                        row,
                        "sessions_that_reached_and_completed_checkout",
                        "Sessions that reached and completed checkout",
                        "Completed checkout",
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
                        "checkout_funnel_source": "shopifyql_sessions",
                    }

            total_reached = sum(item["sessions_reached_checkout"] for item in monthly.values())
            total_completed = sum(item["sessions_completed_checkout"] for item in monthly.values())

            print(
                f"{brand} {year}: ShopifyQL checkout funnel reached={int(total_reached)} "
                f"completed={int(total_completed)}"
            )

            return monthly

        except Exception as exc:
            last_error = exc
            print(f"{brand} {year}: ShopifyQL sessions checkout funnel attempt failed: {exc}")

    print(
        f"{brand} {year}: ShopifyQL checkout funnel unavailable after all attempts. "
        f"Last error: {last_error}"
    )

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
        row["checkout_funnel_source"] = funnel.get("checkout_funnel_source") or "none"

    return rows


def get_shopify_rows(brand: str, store: str, token: str, year: int) -> list[dict]:
    rows = []
    orders = None

    try:
        print(f"Trying Shopify Analytics-style query for {brand} {year}...")
        rows = get_shopify_analytics_monthly(brand, store, token, year)
        print(f"{brand} {year}: Shopify Analytics rows: {len(rows)}")

    except Exception as exc:
        print(f"{brand} {year}: Shopify Analytics query unavailable: {exc}")
        print(f"{brand} {year}: Falling back to Orders API calculations.")

        orders = get_orders(brand=brand, store=store, token=token, year=year)
        print(f"{brand} Shopify orders: {len(orders)}")
        variant_unit_costs = get_variant_unit_costs(store=store, token=token, orders=orders)
        rows = normalize_shopify_orders(
            brand=brand,
            orders=orders,
            year=year,
            variant_unit_costs=variant_unit_costs,
        )

    if orders is None:
        orders = get_orders(brand=brand, store=store, token=token, year=year)
        print(f"{brand} {year}: order activity rows for operational KPIs/COGS: {len(orders)}")

    variant_unit_costs = get_variant_unit_costs(store=store, token=token, orders=orders)
    rows = attach_order_cost_metrics(rows, orders, variant_unit_costs=variant_unit_costs)
    rows = attach_order_activity_metrics(rows, orders)

    checkout_funnel_by_month = get_checkout_funnel_monthly(
        brand=brand,
        store=store,
        token=token,
        year=year,
    )

    rows = attach_checkout_funnel_metrics(rows, checkout_funnel_by_month)

    for row in rows:
        row.setdefault("view_type", "brand")
        row.setdefault("split_type", "brand")
        row.setdefault("split_filter", "All Splits")
        row.setdefault("parent_brand", brand)
        row.setdefault("location_filter", "All Locations")
        row.setdefault("location_id", "")
        row.setdefault("location_name", "")

    return rows
