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


def _split_id_values(value) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = str(value).replace(",", "|").split("|")
    return {str(v).strip() for v in values if str(v).strip() and str(v).strip().lower() not in {"nan", "none", "0"}}


def _merge_id_values(series) -> str:
    values = set()
    for value in series:
        values.update(_split_id_values(value))
    return "|".join(sorted(values))


def _count_id_string(value) -> int:
    return len(_split_id_values(value))


def _prepare_shopify_df(shopify_rows: list[dict]) -> pd.DataFrame:
    required_cols = [
        "brand", "year", "month", "channel", "view_type", "split_type", "split_filter", "parent_brand",
        "location_filter", "location_id", "location_name", "total_sales", "gross_sales",
        "discounts", "returns", "discounts_returns", "shipping_charges", "taxes",
        "net_sales", "cogs", "gross_profit_1", "gross_margin_1",
        "shopify_gross_profit_1_source", "shopify_gross_margin_1_source",
        "transactions", "orders", "units_sold", "customer_id", "customer_ids", "new_customer_ids", "returning_customer_ids",
        "customers", "new_customers", "returning_customers", "sessions_reached_checkout",
        "sessions_completed_checkout", "checkout_abandonments",
    ]

    shopify_df = pd.DataFrame(shopify_rows)
    if shopify_df.empty:
        shopify_df = pd.DataFrame(columns=required_cols)

    for col in required_cols:
        if col not in shopify_df.columns:
            if col in ["brand", "channel", "view_type", "split_type", "split_filter", "parent_brand", "location_filter", "location_id", "location_name", "customer_id", "customer_ids", "new_customer_ids", "returning_customer_ids"]:
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
    shopify_df["location_filter"] = shopify_df["location_filter"].astype(str).str.strip()
    shopify_df["split_filter"] = shopify_df["split_filter"].astype(str).str.strip()

    shopify_df.loc[~location_mask, "location_filter"] = "All Locations"
    shopify_df.loc[~location_mask, "split_filter"] = "All Splits"
    shopify_df.loc[~location_mask, "split_type"] = "brand"

    shopify_df.loc[location_mask & shopify_df["location_filter"].astype(str).eq(""), "location_filter"] = shopify_df.loc[location_mask & shopify_df["location_filter"].astype(str).eq(""), "split_filter"]
    shopify_df.loc[location_mask & shopify_df["location_filter"].astype(str).eq(""), "location_filter"] = "Wellington"
    shopify_df.loc[location_mask & shopify_df["split_filter"].astype(str).eq(""), "split_filter"] = shopify_df.loc[location_mask & shopify_df["split_filter"].astype(str).eq(""), "location_filter"]
    shopify_df.loc[location_mask & shopify_df["split_type"].astype(str).eq(""), "split_type"] = shopify_df.loc[location_mask & shopify_df["split_type"].astype(str).eq(""), "location_filter"].str.lower()

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

    for col in ["brand", "channel", "view_type", "split_type", "split_filter", "parent_brand", "location_filter", "location_id", "location_name", "customer_id", "customer_ids", "new_customer_ids", "returning_customer_ids"]:
        shopify_df[col] = shopify_df[col].astype(str).str.strip()

    # Keep customer identity sets so YTD/quarter totals count unique customers,
    # not the same customer repeated in multiple months.
    missing_customer_ids = shopify_df["customer_ids"].astype(str).str.strip().isin(["", "0", "nan", "None"])
    shopify_df.loc[missing_customer_ids, "customer_ids"] = shopify_df.loc[missing_customer_ids, "customer_id"]
    shopify_df.loc[shopify_df["new_customer_ids"].astype(str).str.strip().isin(["", "0", "nan", "None"]), "new_customer_ids"] = ""
    shopify_df.loc[shopify_df["returning_customer_ids"].astype(str).str.strip().isin(["", "0", "nan", "None"]), "returning_customer_ids"] = ""

    shopify_df["year"] = pd.to_numeric(shopify_df["year"], errors="coerce").fillna(0).astype(int)
    shopify_df["month"] = shopify_df["month"].astype(str).str.zfill(2)
    # COGS should be available in the table. If the row has GP1 and Net Sales but
    # COGS came empty from ShopifyQL, reconstruct COGS as Net Sales - GP1.
    cogs_missing = shopify_df["cogs"].fillna(0).eq(0) & shopify_df["net_sales"].fillna(0).ne(0) & shopify_df["gross_profit_1"].fillna(0).ne(0)
    shopify_df.loc[cogs_missing, "cogs"] = (shopify_df.loc[cogs_missing, "net_sales"] - shopify_df.loc[cogs_missing, "gross_profit_1"]).clip(lower=0)

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
            split_type=("split_type", "first"),
            split_filter=("split_filter", "first"),
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
            customer_ids=("customer_ids", _merge_id_values),
            new_customer_ids=("new_customer_ids", _merge_id_values),
            returning_customer_ids=("returning_customer_ids", _merge_id_values),
            customers=("customers", "sum"),
            new_customers=("new_customers", "sum"),
            returning_customers=("returning_customers", "sum"),
            sessions_reached_checkout=("sessions_reached_checkout", "sum"),
            sessions_completed_checkout=("sessions_completed_checkout", "sum"),
            checkout_abandonments=("checkout_abandonments", "sum"),
        )
    )

    # Prefer unique customer ID counts when available, so Customers matches the
    # selected period instead of summing monthly duplicates.
    grouped["customers_from_ids"] = grouped["customer_ids"].apply(_count_id_string)
    grouped["new_customers_from_ids"] = grouped["new_customer_ids"].apply(_count_id_string)
    grouped["returning_customers_from_ids"] = grouped["returning_customer_ids"].apply(_count_id_string)
    grouped["customers"] = grouped["customers_from_ids"].where(grouped["customers_from_ids"] > 0, grouped["customers"])
    grouped["new_customers"] = grouped["new_customers_from_ids"].where(grouped["new_customers_from_ids"] > 0, grouped["new_customers"])
    grouped["returning_customers"] = grouped["returning_customers_from_ids"].where(grouped["returning_customers_from_ids"] > 0, grouped["returning_customers"])
    grouped.drop(columns=["customers_from_ids", "new_customers_from_ids", "returning_customers_from_ids"], inplace=True, errors="ignore")

    # Ensure COGS is filled for the financial table.
    grouped["cogs"] = grouped["cogs"].where(grouped["cogs"].fillna(0).ne(0), (grouped["net_sales"] - grouped["gross_profit_1"]).clip(lower=0))

    grouped["discount_pct"] = (grouped["discounts"] / grouped["gross_sales"].replace(0, pd.NA)).fillna(0)
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

    brand_mask = result["view_type"].eq("brand")
    location_mask = result["view_type"].eq("location")
    wellington_mask = location_mask & result["location_filter"].astype(str).str.lower().eq("wellington")
    concierge_mask = location_mask & result["location_filter"].astype(str).str.lower().eq("concierge")
    channel_shipping_estimate_mask = wellington_mask | concierge_mask

    def _corro_net_total(year_value, month_value=None) -> float:
        mask = (
            result["view_type"].eq("brand")
            & result["brand"].astype(str).str.lower().eq("corro")
            & result["year"].eq(year_value)
        )
        if month_value is not None and "month" in result.columns:
            mask &= result["month"].astype(str).str.zfill(2).eq(str(month_value).zfill(2))
        return result.loc[mask, "net_sales"].sum()

    # 1) Main business rows: Corro/Cavali brand rows use QuickBooks only.
    #    Shipping Income is Shopify revenue and must not be copied as cost.
    if monthly:
        for (year, month), index in result.groupby(["year", "month"]).groups.items():
            index = list(index)
            brand_index = [i for i in index if bool(brand_mask.loc[i])]
            y_data = _lookup_year_dict(qb_summaries, int(year))
            qb_shipping_total = _safe_float(y_data.get(str(month).zfill(2), 0))
            brand_net_total = result.loc[brand_index, "net_sales"].sum() if brand_index else 0

            for i in brand_index:
                proportion = result.at[i, "net_sales"] / brand_net_total if brand_net_total else 0
                result.at[i, "applied_shipping"] = qb_shipping_total * proportion if qb_shipping_total > 0 else 0.0

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
                result.at[i, "applied_shipping"] = qb_shipping_total * proportion if qb_shipping_total > 0 else 0.0

            marketing_total = sum(_safe_float(v) for v in _lookup_year_dict(marketing_summaries, int(year)).values())
            for i in brand_index:
                proportion = result.at[i, "net_sales"] / brand_net_total if brand_net_total else 0
                result.at[i, "marketing_allocated"] = marketing_total * proportion

    # 2) Location/channel rows: do not inherit global brand marketing by default.
    #    Wellington and Concierge can estimate Shipping Cost from Shopify Shipping
    #    Income only when QuickBooks has no usable separated shipping cost.
    result.loc[location_mask, "applied_shipping"] = 0.0
    result.loc[location_mask, "marketing_allocated"] = 0.0

    if monthly:
        for (year, month), index in result.loc[channel_shipping_estimate_mask].groupby(["year", "month"]).groups.items():
            index = list(index)
            y_data = _lookup_year_dict(qb_summaries, int(year))
            qb_shipping_total = _safe_float(y_data.get(str(month).zfill(2), 0))
            corro_net_total = _corro_net_total(year, month)
            for i in index:
                proportion = result.at[i, "net_sales"] / corro_net_total if corro_net_total else 0
                qb_allocated = qb_shipping_total * proportion if qb_shipping_total > 0 else 0.0
                shopify_estimate = _safe_float(result.at[i, "shipping_charges"])
                result.at[i, "applied_shipping"] = qb_allocated if qb_allocated > 0 else shopify_estimate
    else:
        for year, index in result.loc[channel_shipping_estimate_mask].groupby("year").groups.items():
            index = list(index)
            y_data = _lookup_year_dict(qb_summaries, int(year))
            qb_shipping_total = sum(_safe_float(v) for v in y_data.values())
            corro_net_total = _corro_net_total(year)
            for i in index:
                proportion = result.at[i, "net_sales"] / corro_net_total if corro_net_total else 0
                qb_allocated = qb_shipping_total * proportion if qb_shipping_total > 0 else 0.0
                shopify_estimate = _safe_float(result.at[i, "shipping_charges"])
                result.at[i, "applied_shipping"] = qb_allocated if qb_allocated > 0 else shopify_estimate

    # Cavali should not deduct Ads / Stats in this view for now.
    cavali_mask = result["brand"].astype(str).str.lower().eq("cavali") & result["view_type"].eq("brand")
    result.loc[cavali_mask, "marketing_allocated"] = 0.0

    result["shipping_cost"] = result["applied_shipping"]
    result["shipping_cost_source"] = "QuickBooks"
    result.loc[result["shipping_cost"].fillna(0).eq(0), "shipping_cost_source"] = "QuickBooks unavailable / unmapped"
    result.loc[channel_shipping_estimate_mask & result["shipping_cost"].fillna(0).gt(0), "shipping_cost_source"] = "QuickBooks allocated or Shopify estimate"

    result["ads_stats_spend"] = result["marketing_allocated"]
    result["gross_profit_2"] = result["gross_profit_1"] - result["shipping_cost"]
    result["gross_margin_2"] = (result["gross_profit_2"] / result["net_sales"].replace(0, pd.NA)).fillna(0)
    result["gross_profit_3"] = result["gross_profit_2"] - result["ads_stats_spend"]
    result["gross_margin_3"] = (result["gross_profit_3"] / result["net_sales"].replace(0, pd.NA)).fillna(0)
    result.drop(columns=["applied_shipping", "marketing_allocated"], inplace=True, errors="ignore")
    result = add_estimated_operating_income(result)

    return result



GENERAL_OPEX_PAYROLL_MONTHLY = 40000.0
GENERAL_OPEX_GA_MONTHLY = 45000.0
GENERAL_OPEX_SALES_MARKETING_PCT = 0.0662
GENERAL_OPEX_TECHNOLOGY_MONTHLY = 0.0

CHANNEL_OPEX_POOL_ANNUAL = 70000.0
CONCIERGE_OPEX_BASE_PCT = 0.60
WELLINGTON_OPEX_BASE_PCT = 0.40
CONCIERGE_COMMISSION_PCT = 0.10
WELLINGTON_COMMISSION_PCT = 0.01


def _period_fixed_opex(monthly: bool) -> float:
    months = 1 if monthly else 12
    return months * (GENERAL_OPEX_PAYROLL_MONTHLY + GENERAL_OPEX_GA_MONTHLY + GENERAL_OPEX_TECHNOLOGY_MONTHLY)


def _channel_base_opex(split_name: str, monthly: bool) -> float:
    split = str(split_name or "").strip().lower()
    months_divisor = 12 if monthly else 1
    if split == "concierge":
        return (CHANNEL_OPEX_POOL_ANNUAL * CONCIERGE_OPEX_BASE_PCT) / months_divisor
    if split == "wellington":
        return (CHANNEL_OPEX_POOL_ANNUAL * WELLINGTON_OPEX_BASE_PCT) / months_divisor
    return 0.0


def _channel_commission_opex(split_name: str, net_sales: float) -> float:
    split = str(split_name or "").strip().lower()
    if split == "concierge":
        return _safe_float(net_sales) * CONCIERGE_COMMISSION_PCT
    if split == "wellington":
        return _safe_float(net_sales) * WELLINGTON_COMMISSION_PCT
    return 0.0


def add_estimated_operating_income(df):
    """
    Adds provisional Financial Dashboard OPEX and NOI estimates.

    Financial rules:
    - Brand/main business OPEX pool is allocated by Gross Sales per period:
      Payroll 40k/month + G&A 45k/month + Sales & Marketing 6.62% of Gross Revenue + Technology 0.
    - Concierge OPEX estimate: 70k annual pool * 60%, plus 10% of Concierge Net Sales.
    - Wellington OPEX estimate: 70k annual pool * 40%, plus 1% of Wellington Net Sales.
    - NOI = GP3 - OPEX.
    - NOI % = NOI / Net Sales.
    """
    if df.empty:
        df["estimated_average_opex"] = 0
        df["estimated_net_operating_income"] = 0
        df["estimated_net_operating_income_pct"] = 0
        return df

    df = df.copy()
    df["estimated_average_opex"] = 0.0

    monthly = "month" in df.columns
    group_cols = ["year", "month"] if monthly else ["year"]

    def has_activity(frame):
        return (
            frame["total_sales"].fillna(0).ne(0)
            | frame["gross_sales"].fillna(0).ne(0)
            | frame["net_sales"].fillna(0).ne(0)
        )

    # Main business rows: allocate the general OPEX pool across brand rows by gross sales.
    brand_mask = df["view_type"].astype(str).str.lower().eq("brand") & has_activity(df)
    for _, index in df.loc[brand_mask].groupby(group_cols).groups.items():
        index = list(index)
        period_gross = df.loc[index, "gross_sales"].sum()
        if period_gross <= 0:
            continue
        pool = _period_fixed_opex(monthly=monthly) + (period_gross * GENERAL_OPEX_SALES_MARKETING_PCT)
        for i in index:
            df.at[i, "estimated_average_opex"] = pool * (_safe_float(df.at[i, "gross_sales"]) / period_gross)

    # Channel/location rows: Concierge and Wellington have their own provisional OPEX rules.
    location_mask = df["view_type"].astype(str).str.lower().eq("location") & has_activity(df)
    for i in df.loc[location_mask].index:
        split = df.at[i, "location_filter"] if "location_filter" in df.columns else ""
        df.at[i, "estimated_average_opex"] = _channel_base_opex(split, monthly=monthly) + _channel_commission_opex(split, df.at[i, "net_sales"])

    df["estimated_net_operating_income"] = df["gross_profit_3"] - df["estimated_average_opex"]
    df["estimated_net_operating_income_pct"] = (
        df["estimated_net_operating_income"] / df["net_sales"].replace(0, pd.NA)
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
            split_type=("split_type", "first"),
            split_filter=("split_filter", "first"),
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
    splits_available = sorted(shopify_df.loc[shopify_df["view_type"].eq("location"), "split_filter"].dropna().unique().tolist())
    splits_available = [loc for loc in splits_available if loc and loc != "All Splits"]
    for required_split in ["Wellington", "Concierge"]:
        if required_split not in splits_available:
            splits_available.append(required_split)
        if required_split not in locations_available:
            locations_available.append(required_split)
    years_available = sorted([int(year) for year in shopify_df["year"].dropna().unique().tolist() if int(year) > 0])

    concierge_debug = shopify_df[(shopify_df["view_type"].eq("location")) & (shopify_df["split_filter"].str.lower().eq("concierge"))]
    if not concierge_debug.empty:
        print(
            "Financial transform Concierge rows:",
            len(concierge_debug),
            "sales=", round(concierge_debug["total_sales"].sum(), 2),
            "months=", sorted(concierge_debug["month"].dropna().unique().tolist()),
        )
    else:
        print("Financial transform Concierge rows: 0")

    for frame in [shopify_by_brand_year, shopify_by_brand_month]:
        if "shipping_cost" not in frame.columns:
            frame["shipping_cost"] = 0
        if "ads_stats_spend" not in frame.columns:
            frame["ads_stats_spend"] = 0
        if "estimated_average_opex" not in frame.columns:
            frame["estimated_average_opex"] = 0
            frame["estimated_net_operating_income"] = frame.get("gross_profit_3", 0)
            frame["estimated_net_operating_income_pct"] = (
                frame["estimated_net_operating_income"] / frame["net_sales"].replace(0, pd.NA)
            ).fillna(0)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "brands_available": brands_available,
        "locations_available": locations_available,
        "splits_available": splits_available,
        "years_available": years_available,
        "shopify_kpis_by_brand_year": shopify_by_brand_year.to_dict(orient="records"),
        "shopify_kpis_by_brand_month": shopify_by_brand_month.to_dict(orient="records"),
        "shopify_by_channel": shopify_by_channel.to_dict(orient="records"),
        "qb_summary": qb_summaries,
        "marketing_summary": marketing_summaries,
        "bill_rows": bill_rows,
    }
