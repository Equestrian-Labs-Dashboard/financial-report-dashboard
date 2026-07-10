from datetime import datetime, timezone
import pandas as pd


def _empty_months() -> dict[str, float]:
    return {f"{month:02d}": 0.0 for month in range(1, 13)}


def _lookup_year_dict(source: dict, year: int) -> dict:
    return source.get(year, source.get(str(year), _empty_months())) or _empty_months()


def _safe_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _prepare_shopify_df(shopify_rows: list[dict]) -> pd.DataFrame:
    required_cols = [
        "brand", "year", "month", "channel", "view_type", "parent_brand",
        "location_filter", "location_id", "location_name", "total_sales", "gross_sales",
        "discounts", "returns", "discounts_returns", "shipping_charges", "taxes",
        "net_sales", "cogs", "gross_profit_1", "gross_margin_1",
        "shopify_gross_profit_1_source", "shopify_gross_margin_1_source",
        "transactions", "orders", "units_sold",
        "customers", "new_customers", "returning_customers", "sessions_reached_checkout",
        "sessions_completed_checkout", "checkout_abandonments",
    ]

    shopify_df = pd.DataFrame(shopify_rows)
    if shopify_df.empty:
        shopify_df = pd.DataFrame(columns=required_cols)

    for col in required_cols:
        if col not in shopify_df.columns:
            if col in ["brand", "channel", "view_type", "parent_brand", "location_filter", "location_id", "location_name"]:
                shopify_df[col] = ""
            else:
                shopify_df[col] = 0

    shopify_df["view_type"] = shopify_df["view_type"].replace("", "brand").fillna("brand")
    shopify_df["parent_brand"] = shopify_df["parent_brand"].fillna("")
    shopify_df["parent_brand"] = shopify_df["parent_brand"].where(shopify_df["parent_brand"].astype(str).ne(""), shopify_df["brand"])

    # Backward compatibility: if an older Wellington file had brand="Wellington",
    # convert it into second-filter rows using parent_brand as Corro/Cavali.
    old_wellington_mask = shopify_df["brand"].astype(str).eq("Wellington") & shopify_df["parent_brand"].astype(str).ne("")
    shopify_df.loc[old_wellington_mask, "brand"] = shopify_df.loc[old_wellington_mask, "parent_brand"]
    shopify_df.loc[old_wellington_mask, "view_type"] = "location"

    location_mask = shopify_df["view_type"].astype(str).eq("location")
    shopify_df.loc[~location_mask, "location_filter"] = "All Locations"
    shopify_df.loc[location_mask & shopify_df["location_filter"].astype(str).eq(""), "location_filter"] = "Wellington"

    numeric_cols = [
        "total_sales", "gross_sales", "discounts", "returns", "discounts_returns",
        "shipping_charges", "taxes", "net_sales", "cogs", "gross_profit_1", "gross_margin_1",
        "shopify_gross_profit_1_source", "shopify_gross_margin_1_source",
        "transactions", "units_sold", "customers", "new_customers", "returning_customers",
        "sessions_reached_checkout", "sessions_completed_checkout", "checkout_abandonments",
    ]
    for col in numeric_cols:
        shopify_df[col] = pd.to_numeric(shopify_df[col], errors="coerce").fillna(0)

    if "orders" in shopify_df.columns:
        shopify_df["orders"] = shopify_df["orders"].where(shopify_df["orders"] > 0, shopify_df["transactions"])

    for col in ["brand", "channel", "view_type", "parent_brand", "location_filter", "location_id", "location_name"]:
        shopify_df[col] = shopify_df[col].astype(str)

    shopify_df["year"] = pd.to_numeric(shopify_df["year"], errors="coerce").fillna(0).astype(int)
    shopify_df["month"] = shopify_df["month"].astype(str).str.zfill(2)
    shopify_df["checkout_abandonments"] = (shopify_df["sessions_reached_checkout"] - shopify_df["sessions_completed_checkout"]).clip(lower=0)
    return shopify_df


def _aggregate_shopify(shopify_df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if shopify_df.empty:
        return pd.DataFrame(columns=group_cols)

    shopify_df = shopify_df.copy()
    shopify_df["gross_margin_1_weighted"] = shopify_df["gross_margin_1"] * shopify_df["net_sales"]

    grouped = (
        shopify_df
        .groupby(group_cols, as_index=False)
        .agg(
            parent_brand=("parent_brand", "first"),
            location_id=("location_id", "first"),
            location_name=("location_name", "first"),
            total_sales=("total_sales", "sum"),
            gross_sales=("gross_sales", "sum"),
            discounts=("discounts", "sum"),
            returns=("returns", "sum"),
            discounts_returns=("discounts_returns", "sum"),
            shipping_charges=("shipping_charges", "sum"),
            taxes=("taxes", "sum"),
            net_sales=("net_sales", "sum"),
            cogs=("cogs", "sum"),
            gross_profit_1=("gross_profit_1", "sum"),
            gross_margin_1_weighted=("gross_margin_1_weighted", "sum"),
            shopify_gross_profit_1_source=("shopify_gross_profit_1_source", "max"),
            shopify_gross_margin_1_source=("shopify_gross_margin_1_source", "max"),
            transactions=("transactions", "sum"),
            units_sold=("units_sold", "sum"),
            customers=("customers", "sum"),
            new_customers=("new_customers", "sum"),
            returning_customers=("returning_customers", "sum"),
            sessions_reached_checkout=("sessions_reached_checkout", "sum"),
            sessions_completed_checkout=("sessions_completed_checkout", "sum"),
            checkout_abandonments=("checkout_abandonments", "sum"),
        )
    )

    grouped["discounts_returns_pct"] = (grouped["discounts_returns"] / grouped["gross_sales"].replace(0, pd.NA)).fillna(0)
    # Preserve Shopify Gross Margin 1 when ShopifyQL provides it. For grouped
    # views, use the net-sales-weighted average of the Shopify monthly margin.
    grouped["gross_margin_1"] = (grouped["gross_margin_1_weighted"] / grouped["net_sales"].replace(0, pd.NA)).fillna(0)
    no_shopify_margin = grouped["shopify_gross_margin_1_source"].fillna(0).eq(0)
    grouped.loc[no_shopify_margin, "gross_margin_1"] = (
        grouped.loc[no_shopify_margin, "gross_profit_1"] / grouped.loc[no_shopify_margin, "net_sales"].replace(0, pd.NA)
    ).fillna(0)
    grouped.drop(columns=["gross_margin_1_weighted"], inplace=True, errors="ignore")
    grouped["net_gross_ratio"] = (grouped["net_sales"] / grouped["gross_sales"].replace(0, pd.NA)).fillna(0)
    grouped["checkout_abandonment_rate"] = (grouped["checkout_abandonments"] / grouped["sessions_reached_checkout"].replace(0, pd.NA)).fillna(0)
    return grouped


def _add_margin_2_and_3(grouped: pd.DataFrame, qb_summaries: dict, marketing_summaries: dict, monthly: bool) -> pd.DataFrame:
    if grouped.empty:
        return grouped

    result = grouped.copy()
    result["applied_shipping"] = 0.0
    result["marketing_allocated"] = 0.0

    # Brand rows keep the original Google Sheet / QB allocation logic.
    # Location rows, including Wellington, are not allocated global marketing.
    brand_mask = result["view_type"].eq("brand")
    location_mask = result["view_type"].eq("location")

    if monthly:
        for (year, month), index in result.groupby(["year", "month"]).groups.items():
            index = list(index)
            brand_index = [i for i in index if bool(brand_mask.loc[i])]
            y_data = _lookup_year_dict(qb_summaries, int(year))
            qb_shipping_total = _safe_float(y_data.get(str(month).zfill(2), 0))
            brand_net_total = result.loc[brand_index, "net_sales"].sum() if brand_index else 0

            for i in brand_index:
                proportion = result.at[i, "net_sales"] / brand_net_total if brand_net_total else 0
                result.at[i, "applied_shipping"] = qb_shipping_total * proportion

            marketing_total = _safe_float(_lookup_year_dict(marketing_summaries, int(year)).get(str(month).zfill(2), 0))
            for i in brand_index:
                proportion = result.at[i, "net_sales"] / brand_net_total if brand_net_total else 0
                result.at[i, "marketing_allocated"] = marketing_total * proportion
    else:
        for year, index in result.groupby("year").groups.items():
            index = list(index)
            brand_index = [i for i in index if bool(brand_mask.loc[i])]
            y_data = _lookup_year_dict(qb_summaries, int(year))
            qb_shipping_total = sum(_safe_float(v) for v in y_data.values())
            brand_net_total = result.loc[brand_index, "net_sales"].sum() if brand_index else 0

            for i in brand_index:
                proportion = result.at[i, "net_sales"] / brand_net_total if brand_net_total else 0
                result.at[i, "applied_shipping"] = qb_shipping_total * proportion

            marketing_total = sum(_safe_float(v) for v in _lookup_year_dict(marketing_summaries, int(year)).values())
            for i in brand_index:
                proportion = result.at[i, "net_sales"] / brand_net_total if brand_net_total else 0
                result.at[i, "marketing_allocated"] = marketing_total * proportion

    # Wellington should not include shipping or Ads / Stats unless an approved
    # Wellington-specific campaign is added later. Concierge keeps Shopify
    # Shipping Income, but does not receive allocated global shipping/ads.
    wellington_mask = location_mask & result["location_filter"].astype(str).str.lower().eq("wellington")
    result.loc[wellington_mask, "shipping_charges"] = 0.0
    result.loc[location_mask, "applied_shipping"] = 0.0
    result.loc[location_mask, "marketing_allocated"] = 0.0

    # Cavali should not deduct Ads / Stats in this view for now.
    cavali_mask = result["brand"].astype(str).str.lower().eq("cavali") & result["view_type"].eq("brand")
    result.loc[cavali_mask, "marketing_allocated"] = 0.0

    # Keep these visible in the financial table.
    # Shipping Cost sits under GM1 and is the adjustment used to get GP2.
    # Ads / Stats sits under GM2 and is the adjustment used to get GP3.
    result["shipping_cost"] = result["applied_shipping"]
    result["ads_stats_spend"] = result["marketing_allocated"]

    result["gross_profit_2"] = result["gross_profit_1"] - result["shipping_cost"]
    result["gross_margin_2"] = (result["gross_profit_2"] / result["net_sales"].replace(0, pd.NA)).fillna(0)
    result["gross_profit_3"] = result["gross_profit_2"] - result["ads_stats_spend"]
    result["gross_margin_3"] = (result["gross_profit_3"] / result["net_sales"].replace(0, pd.NA)).fillna(0)
    result.drop(columns=["applied_shipping", "marketing_allocated"], inplace=True, errors="ignore")
    result = add_estimated_operating_income(result)

    return result



ESTIMATED_OPEX_RULES = {
    "Corro": {"amount": 100000, "period": "monthly"},
    "Cavali": {"amount": 17500, "period": "quarterly"},
}


def add_estimated_operating_income(df):
    """
    Adds provisional operating estimates after GP3/GM3.

    Current provisional rules:
    - Corro: 100,000 per month
    - Cavali: 17,500 per quarter, allocated as 17,500 / 3 per month
    - Wellington/location rows: 0, so location view does not double-count brand OPEX.
    """
    if df.empty:
        df["estimated_average_opex"] = 0
        df["estimated_net_operating_income"] = 0
        df["estimated_net_operating_income_pct"] = 0
        return df

    def monthly_opex(row):
        view_type = str(row.get("view_type", "brand"))
        if view_type == "location":
            return 0.0

        has_activity = (
            _safe_float(row.get("total_sales")) != 0 or
            _safe_float(row.get("gross_sales")) != 0 or
            _safe_float(row.get("net_sales")) != 0
        )
        if not has_activity:
            return 0.0

        brand = str(row.get("brand", ""))
        rule = ESTIMATED_OPEX_RULES.get(brand)
        if not rule:
            return 0.0

        amount = _safe_float(rule.get("amount"))
        period = str(rule.get("period"))

        if period == "monthly":
            return amount
        if period == "quarterly":
            return amount / 3

        return 0.0

    df["estimated_average_opex"] = df.apply(monthly_opex, axis=1)
    df["estimated_net_operating_income"] = df["gross_profit_3"] - df["estimated_average_opex"]
    df["estimated_net_operating_income_pct"] = (
        df["estimated_net_operating_income"] / df["total_sales"].replace(0, pd.NA)
    ).fillna(0)

    return df


def build_financial_report(shopify_rows: list[dict], bill_rows: list[dict], qb_summaries: dict, marketing_summaries: dict | None = None) -> dict:
    marketing_summaries = marketing_summaries or {}
    shopify_df = _prepare_shopify_df(shopify_rows)

    group_year = ["brand", "view_type", "location_filter", "year"]
    group_month = ["brand", "view_type", "location_filter", "year", "month"]

    shopify_by_brand_year = _add_margin_2_and_3(_aggregate_shopify(shopify_df, group_year), qb_summaries, marketing_summaries, monthly=False)
    shopify_by_brand_month = _add_margin_2_and_3(_aggregate_shopify(shopify_df, group_month), qb_summaries, marketing_summaries, monthly=True)

    shopify_by_channel = (
        shopify_df
        .groupby(["brand", "view_type", "location_filter", "year", "month", "channel"], as_index=False)
        .agg(
            parent_brand=("parent_brand", "first"),
            total_sales=("total_sales", "sum"),
            gross_sales=("gross_sales", "sum"),
            net_sales=("net_sales", "sum"),
            orders=("orders", "sum"),
            transactions=("transactions", "sum"),
        )
    ) if not shopify_df.empty else pd.DataFrame()

    brands_available = sorted(shopify_df.loc[shopify_df["view_type"].eq("brand"), "brand"].dropna().unique().tolist())
    locations_available = sorted(shopify_df.loc[shopify_df["view_type"].eq("location"), "location_filter"].dropna().unique().tolist())
    locations_available = [loc for loc in locations_available if loc and loc != "All Locations"]
    years_available = sorted([int(year) for year in shopify_df["year"].dropna().unique().tolist() if int(year) > 0])

    for frame in [shopify_by_brand_year, shopify_by_brand_month]:
        if "shipping_cost" not in frame.columns:
            frame["shipping_cost"] = 0
        if "ads_stats_spend" not in frame.columns:
            frame["ads_stats_spend"] = 0
        if "estimated_average_opex" not in frame.columns:
            frame["estimated_average_opex"] = 0
            frame["estimated_net_operating_income"] = frame.get("gross_profit_3", 0)
            frame["estimated_net_operating_income_pct"] = (
                frame["estimated_net_operating_income"] / frame["total_sales"].replace(0, pd.NA)
            ).fillna(0)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "brands_available": brands_available,
        "locations_available": locations_available,
        "years_available": years_available,
        "shopify_kpis_by_brand_year": shopify_by_brand_year.to_dict(orient="records"),
        "shopify_kpis_by_brand_month": shopify_by_brand_month.to_dict(orient="records"),
        "shopify_by_channel": shopify_by_channel.to_dict(orient="records"),
        "qb_summary": qb_summaries,
        "marketing_summary": marketing_summaries,
        "bill_rows": bill_rows,
    }
