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
    shopify_df = pd.DataFrame(shopify_rows)

    required_cols = [
        "brand", "year", "month", "channel", "view_type", "parent_brand",
        "location_id", "location_name", "total_sales", "gross_sales", "discounts",
        "returns", "discounts_returns", "shipping_charges", "taxes", "net_sales",
        "cogs", "gross_profit_1", "transactions", "units_sold", "customers",
        "new_customers", "returning_customers", "sessions_reached_checkout",
        "sessions_completed_checkout", "checkout_abandonments",
    ]

    if shopify_df.empty:
        shopify_df = pd.DataFrame(columns=required_cols)

    for col in required_cols:
        if col not in shopify_df.columns:
            if col in ["brand", "channel", "view_type", "parent_brand", "location_id", "location_name"]:
                shopify_df[col] = ""
            else:
                shopify_df[col] = 0

    shopify_df["view_type"] = shopify_df["view_type"].replace("", "brand").fillna("brand")
    shopify_df["parent_brand"] = shopify_df["parent_brand"].fillna(shopify_df["brand"])

    numeric_cols = [
        "total_sales", "gross_sales", "discounts", "returns", "discounts_returns",
        "shipping_charges", "taxes", "net_sales", "cogs", "gross_profit_1",
        "transactions", "units_sold", "customers", "new_customers", "returning_customers",
        "sessions_reached_checkout", "sessions_completed_checkout", "checkout_abandonments",
    ]

    for col in numeric_cols:
        shopify_df[col] = pd.to_numeric(shopify_df[col], errors="coerce").fillna(0)

    shopify_df["brand"] = shopify_df["brand"].astype(str)
    shopify_df["channel"] = shopify_df["channel"].astype(str)
    shopify_df["view_type"] = shopify_df["view_type"].astype(str)
    shopify_df["parent_brand"] = shopify_df["parent_brand"].astype(str)
    shopify_df["location_id"] = shopify_df["location_id"].astype(str)
    shopify_df["location_name"] = shopify_df["location_name"].astype(str)
    shopify_df["year"] = pd.to_numeric(shopify_df["year"], errors="coerce").fillna(0).astype(int)
    shopify_df["month"] = shopify_df["month"].astype(str).str.zfill(2)

    # Shopify checkout funnel formula requested by the team.
    shopify_df["checkout_abandonments"] = (
        shopify_df["sessions_reached_checkout"] - shopify_df["sessions_completed_checkout"]
    ).clip(lower=0)

    return shopify_df


def _aggregate_shopify(shopify_df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if shopify_df.empty:
        return pd.DataFrame(columns=group_cols)

    grouped = (
        shopify_df
        .groupby(group_cols, as_index=False)
        .agg(
            view_type=("view_type", "first"),
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

    grouped["discounts_returns_pct"] = (
        grouped["discounts_returns"] / grouped["gross_sales"].replace(0, pd.NA)
    ).fillna(0)

    grouped["gross_margin_1"] = (
        grouped["gross_profit_1"] / grouped["net_sales"].replace(0, pd.NA)
    ).fillna(0)

    grouped["net_gross_ratio"] = (
        grouped["net_sales"] / grouped["gross_sales"].replace(0, pd.NA)
    ).fillna(0)

    grouped["checkout_abandonment_rate"] = (
        grouped["checkout_abandonments"] / grouped["sessions_reached_checkout"].replace(0, pd.NA)
    ).fillna(0)

    return grouped


def _add_margin_2_and_3(
    grouped: pd.DataFrame,
    qb_summaries: dict,
    marketing_summaries: dict,
    monthly: bool,
) -> pd.DataFrame:
    if grouped.empty:
        return grouped

    result = grouped.copy()
    result["applied_shipping"] = 0.0
    result["marketing_allocated"] = 0.0

    # Brand rows use QB shipping allocation when available.
    # Location rows, including Wellington, do not allocate global brand spend into the location.
    # Wellington GP3 = GP2 because there is no dedicated marketing allocation here.
    brand_mask = result["view_type"].ne("location")
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
                result.at[i, "applied_shipping"] = (
                    qb_shipping_total * proportion if qb_shipping_total > 0 else result.at[i, "shipping_charges"]
                )

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
                result.at[i, "applied_shipping"] = (
                    qb_shipping_total * proportion if qb_shipping_total > 0 else result.at[i, "shipping_charges"]
                )

            marketing_total = sum(_safe_float(v) for v in _lookup_year_dict(marketing_summaries, int(year)).values())
            for i in brand_index:
                proportion = result.at[i, "net_sales"] / brand_net_total if brand_net_total else 0
                result.at[i, "marketing_allocated"] = marketing_total * proportion

    # For Wellington/location rows, use their own Shopify shipping and no marketing allocation.
    result.loc[location_mask, "applied_shipping"] = result.loc[location_mask, "shipping_charges"]
    result.loc[location_mask, "marketing_allocated"] = 0.0

    result["gross_profit_2"] = result["gross_profit_1"] - result["applied_shipping"]
    result["gross_margin_2"] = (
        result["gross_profit_2"] / result["net_sales"].replace(0, pd.NA)
    ).fillna(0)

    result["gross_profit_3"] = result["gross_profit_2"] - result["marketing_allocated"]
    result["gross_margin_3"] = (
        result["gross_profit_3"] / result["net_sales"].replace(0, pd.NA)
    ).fillna(0)

    result.drop(columns=["applied_shipping", "marketing_allocated"], inplace=True, errors="ignore")

    return result


def build_financial_report(
    shopify_rows: list[dict],
    bill_rows: list[dict],
    qb_summaries: dict,
    marketing_summaries: dict | None = None,
) -> dict:
    marketing_summaries = marketing_summaries or {}

    shopify_df = _prepare_shopify_df(shopify_rows)

    shopify_by_brand_year = _aggregate_shopify(shopify_df, ["brand", "year"])
    shopify_by_brand_year = _add_margin_2_and_3(
        shopify_by_brand_year,
        qb_summaries=qb_summaries,
        marketing_summaries=marketing_summaries,
        monthly=False,
    )

    shopify_by_brand_month = _aggregate_shopify(shopify_df, ["brand", "year", "month"])
    shopify_by_brand_month = _add_margin_2_and_3(
        shopify_by_brand_month,
        qb_summaries=qb_summaries,
        marketing_summaries=marketing_summaries,
        monthly=True,
    )

    shopify_by_channel = (
        shopify_df
        .groupby(["brand", "year", "month", "channel"], as_index=False)
        .agg(
            view_type=("view_type", "first"),
            parent_brand=("parent_brand", "first"),
            total_sales=("total_sales", "sum"),
            gross_sales=("gross_sales", "sum"),
            net_sales=("net_sales", "sum"),
            transactions=("transactions", "sum"),
        )
    ) if not shopify_df.empty else pd.DataFrame()

    brands_available = sorted(
        shopify_df.loc[shopify_df["view_type"].ne("location"), "brand"]
        .dropna()
        .unique()
        .tolist()
    )

    locations_available = sorted(
        shopify_df.loc[shopify_df["view_type"].eq("location"), "brand"]
        .dropna()
        .unique()
        .tolist()
    )

    # Keep Wellington available in the same brand selector without making Dashboard / All Brands double count it.
    selector_entities = brands_available + [loc for loc in locations_available if loc not in brands_available]

    years_available = sorted([
        int(year)
        for year in shopify_df["year"].dropna().unique().tolist()
        if int(year) > 0
    ])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "brands_available": selector_entities,
        "brand_entities": brands_available,
        "locations_available": locations_available,
        "years_available": years_available,
        "shopify_kpis_by_brand_year": shopify_by_brand_year.to_dict(orient="records"),
        "shopify_kpis_by_brand_month": shopify_by_brand_month.to_dict(orient="records"),
        "shopify_by_channel": shopify_by_channel.to_dict(orient="records"),
        "qb_summary": qb_summaries,
        "marketing_summary": marketing_summaries,
        "bill_rows": bill_rows,
    }
