from datetime import datetime, timezone
import pandas as pd


def build_financial_report(
    shopify_rows: list[dict],
    bill_rows: list[dict],
    qb_summaries: dict,
) -> dict:
    shopify_df = pd.DataFrame(shopify_rows)

    if shopify_df.empty:
        shopify_df = pd.DataFrame(columns=[
            "brand", "year", "month", "channel",
            "total_sales", "gross_sales", "discounts", "returns",
            "discounts_returns", "discounts_returns_pct",
            "shipping_charges", "taxes", "net_sales", "cogs",
            "gross_profit_1", "gross_margin_1", "transactions",
            "sessions_reached_checkout",
            "sessions_completed_checkout",
            "checkout_abandonments",
            "checkout_abandonment_rate",
        ])

    required_cols = [
        "brand", "year", "month", "channel",
        "total_sales", "gross_sales", "discounts", "returns",
        "discounts_returns", "shipping_charges", "taxes",
        "net_sales", "cogs", "gross_profit_1", "transactions",
        "sessions_reached_checkout",
        "sessions_completed_checkout",
        "checkout_abandonments",
    ]

    for col in required_cols:
        if col not in shopify_df.columns:
            shopify_df[col] = 0

    numeric_cols = [
        "total_sales",
        "gross_sales",
        "discounts",
        "returns",
        "discounts_returns",
        "shipping_charges",
        "taxes",
        "net_sales",
        "cogs",
        "gross_profit_1",
        "transactions",
        "sessions_reached_checkout",
        "sessions_completed_checkout",
        "checkout_abandonments",
    ]

    for col in numeric_cols:
        shopify_df[col] = pd.to_numeric(shopify_df[col], errors="coerce").fillna(0)

    shopify_df["brand"] = shopify_df["brand"].astype(str)
    shopify_df["channel"] = shopify_df["channel"].astype(str)
    shopify_df["year"] = pd.to_numeric(shopify_df["year"], errors="coerce").fillna(0).astype(int)
    shopify_df["month"] = shopify_df["month"].astype(str).str.zfill(2)

    # Recalculate abandonment count from Shopify session funnel when reached/completed are present.
    # Formula requested:
    # Checkout Abandonments = sessions_reached_checkout - sessions_completed_checkout
    # Checkout Abandonment Rate = Checkout Abandonments / sessions_reached_checkout
    shopify_df["checkout_abandonments"] = (
        shopify_df["sessions_reached_checkout"] - shopify_df["sessions_completed_checkout"]
    ).clip(lower=0)

    shopify_by_brand_year = (
        shopify_df
        .groupby(["brand", "year"], as_index=False)
        .agg(
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
            sessions_reached_checkout=("sessions_reached_checkout", "sum"),
            sessions_completed_checkout=("sessions_completed_checkout", "sum"),
            checkout_abandonments=("checkout_abandonments", "sum"),
        )
    )

    shopify_by_brand_year["discounts_returns_pct"] = (
        shopify_by_brand_year["discounts_returns"]
        / shopify_by_brand_year["gross_sales"].replace(0, pd.NA)
    ).fillna(0)

    shopify_by_brand_year["gross_margin_1"] = (
        shopify_by_brand_year["gross_profit_1"]
        / shopify_by_brand_year["net_sales"].replace(0, pd.NA)
    ).fillna(0)

    shopify_by_brand_year["net_gross_ratio"] = (
        shopify_by_brand_year["net_sales"]
        / shopify_by_brand_year["gross_sales"].replace(0, pd.NA)
    ).fillna(0)

    shopify_by_brand_year["checkout_abandonment_rate"] = (
        shopify_by_brand_year["checkout_abandonments"]
        / shopify_by_brand_year["sessions_reached_checkout"].replace(0, pd.NA)
    ).fillna(0)

    shopify_by_brand_month = (
        shopify_df
        .groupby(["brand", "year", "month"], as_index=False)
        .agg(
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
            sessions_reached_checkout=("sessions_reached_checkout", "sum"),
            sessions_completed_checkout=("sessions_completed_checkout", "sum"),
            checkout_abandonments=("checkout_abandonments", "sum"),
        )
    )

    shopify_by_brand_month["discounts_returns_pct"] = (
        shopify_by_brand_month["discounts_returns"]
        / shopify_by_brand_month["gross_sales"].replace(0, pd.NA)
    ).fillna(0)

    shopify_by_brand_month["gross_margin_1"] = (
        shopify_by_brand_month["gross_profit_1"]
        / shopify_by_brand_month["net_sales"].replace(0, pd.NA)
    ).fillna(0)

    shopify_by_brand_month["net_gross_ratio"] = (
        shopify_by_brand_month["net_sales"]
        / shopify_by_brand_month["gross_sales"].replace(0, pd.NA)
    ).fillna(0)

    shopify_by_brand_month["checkout_abandonment_rate"] = (
        shopify_by_brand_month["checkout_abandonments"]
        / shopify_by_brand_month["sessions_reached_checkout"].replace(0, pd.NA)
    ).fillna(0)

    shopify_by_channel = (
        shopify_df
        .groupby(["brand", "year", "month", "channel"], as_index=False)
        .agg(
            total_sales=("total_sales", "sum"),
            gross_sales=("gross_sales", "sum"),
            net_sales=("net_sales", "sum"),
            transactions=("transactions", "sum"),
        )
    )

    brands_available = sorted(shopify_df["brand"].dropna().unique().tolist())
    years_available = sorted([
        int(year)
        for year in shopify_df["year"].dropna().unique().tolist()
        if int(year) > 0
    ])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "brands_available": brands_available,
        "years_available": years_available,
        "shopify_kpis_by_brand_year": shopify_by_brand_year.to_dict(orient="records"),
        "shopify_kpis_by_brand_month": shopify_by_brand_month.to_dict(orient="records"),
        "shopify_by_channel": shopify_by_channel.to_dict(orient="records"),
        "qb_summary": qb_summaries,
        "bill_rows": bill_rows,
    }
