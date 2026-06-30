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
            "discounts_returns", "shipping_charges", "taxes",
            "net_sales", "cogs", "gross_profit_1", "transactions",
            "sessions_reached_checkout", "sessions_completed_checkout",
            "checkout_abandonments",
        ])

    required_cols = [
        "brand", "year", "month", "channel",
        "total_sales", "gross_sales", "discounts", "returns",
        "discounts_returns", "shipping_charges", "taxes",
        "net_sales", "cogs", "gross_profit_1", "transactions",
        "sessions_reached_checkout", "sessions_completed_checkout",
        "checkout_abandonments",
    ]

    for col in required_cols:
        if col not in shopify_df.columns:
            shopify_df[col] = 0

    numeric_cols = [
        "total_sales", "gross_sales", "discounts", "returns",
        "discounts_returns", "shipping_charges", "taxes",
        "net_sales", "cogs", "gross_profit_1", "transactions",
        "sessions_reached_checkout", "sessions_completed_checkout",
        "checkout_abandonments",
    ]

    for col in numeric_cols:
        shopify_df[col] = pd.to_numeric(shopify_df[col], errors="coerce").fillna(0)

    shopify_df["brand"] = shopify_df["brand"].astype(str)
    shopify_df["year"] = pd.to_numeric(shopify_df["year"], errors="coerce").fillna(0).astype(int)
    shopify_df["month"] = shopify_df["month"].astype(str).str.zfill(2)

    # Agrupación mensual
    shopify_by_brand_month = (
        shopify_df
        .groupby(["brand", "year", "month"], as_index=False)
        .agg({col: "sum" for col in numeric_cols})
    )

    # Cálculos GP1 / GM1
    shopify_by_brand_month["gross_margin_1"] = (
        shopify_by_brand_month["gross_profit_1"]
        / shopify_by_brand_month["net_sales"].replace(0, pd.NA)
    ).fillna(0)

    # Cálculos GP2 / GM2 (QuickBooks)
    def get_qb_shipping(row):
        y = str(int(row['year']))
        m = row['month']
        try:
            return float(qb_summaries.get(y, {}).get(m, 0.0))
        except:
            return 0.0

    shopify_by_brand_month['shipping_cost_qb'] = shopify_by_brand_month.apply(get_qb_shipping, axis=1)
    shopify_by_brand_month['gross_profit_2'] = shopify_by_brand_month['gross_profit_1'] - shopify_by_brand_month['shipping_cost_qb']
    shopify_by_brand_month['gross_margin_2'] = (
        shopify_by_brand_month['gross_profit_2']
        / shopify_by_brand_month["net_sales"].replace(0, pd.NA)
    ).fillna(0)

    # GP3 / GM3 (Inicializados iguales a GP2 para que el sistema no falle)
    shopify_by_brand_month['gross_profit_3'] = shopify_by_brand_month['gross_profit_2']
    shopify_by_brand_month['gross_margin_3'] = shopify_by_brand_month['gross_margin_2']

    brands_available = sorted(shopify_df["brand"].dropna().unique().tolist())
    years_available = sorted([int(y) for y in shopify_df["year"].dropna().unique().tolist() if int(y) > 0])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "brands_available": brands_available,
        "years_available": years_available,
        "shopify_kpis_by_brand_month": shopify_by_brand_month.to_dict(orient="records"),
        "qb_summary": qb_summaries,
        "bill_rows": bill_rows,
    }
