from datetime import datetime, timezone
import pandas as pd

def build_financial_report(
    shopify_rows: list[dict],
    bill_rows: list[dict],
    qb_summaries: dict,
    marketing_summaries: dict,
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

    # Recalculate abandonment count
    shopify_df["checkout_abandonments"] = (
        shopify_df["sessions_reached_checkout"] - shopify_df["sessions_completed_checkout"]
    ).clip(lower=0)

    # ---------------------------------------------------------
    # 1. AGRUPACIÓN ANUAL (YEAR)
    # ---------------------------------------------------------
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

    # --- LÓGICA DE GROSS MARGIN 2 y 3 (ANUAL) ---
    def get_qb_shipping_year(row):
        y = str(int(row['year']))
        y_data = qb_summaries.get(y, qb_summaries.get(int(y), {}))
        return sum(float(v) for v in y_data.values())

    shopify_by_brand_year['qb_shipping_total'] = shopify_by_brand_year.apply(get_qb_shipping_year, axis=1)
    yearly_totals = shopify_by_brand_year.groupby(['year'])['net_sales'].transform('sum')
    shopify_by_brand_year['sales_proportion'] = (shopify_by_brand_year['net_sales'] / yearly_totals.replace(0, pd.NA)).fillna(0)
    shopify_by_brand_year['qb_shipping_allocated'] = shopify_by_brand_year['qb_shipping_total'] * shopify_by_brand_year['sales_proportion']

    # Usa QB si es mayor a 0, de lo contrario usa los datos de Shopify
    shopify_by_brand_year['applied_shipping'] = shopify_by_brand_year.apply(
        lambda x: x['qb_shipping_allocated'] if x['qb_shipping_total'] > 0 else x['shipping_charges'], axis=1
    )

    shopify_by_brand_year['gross_profit_2'] = shopify_by_brand_year['gross_profit_1'] - shopify_by_brand_year['applied_shipping']
    shopify_by_brand_year['gross_margin_2'] = (shopify_by_brand_year['gross_profit_2'] / shopify_by_brand_year['net_sales'].replace(0, pd.NA)).fillna(0)

    def get_marketing_year(row):
        y = str(int(row['year']))
        y_data = marketing_summaries.get(y, marketing_summaries.get(int(y), {}))
        return sum(float(v) for v in y_data.values())

    shopify_by_brand_year['marketing_spend_total'] = shopify_by_brand_year.apply(get_marketing_year, axis=1)
    shopify_by_brand_year['marketing_allocated'] = shopify_by_brand_year['marketing_spend_total'] * shopify_by_brand_year['sales_proportion']

    shopify_by_brand_year['gross_profit_3'] = shopify_by_brand_year['gross_profit_2'] - shopify_by_brand_year['marketing_allocated']
    shopify_by_brand_year['gross_margin_3'] = (shopify_by_brand_year['gross_profit_3'] / shopify_by_brand_year['net_sales'].replace(0, pd.NA)).fillna(0)

    # Limpieza de columnas temporales
    shopify_by_brand_year.drop(columns=['qb_shipping_total', 'sales_proportion', 'qb_shipping_allocated', 'applied_shipping', 'marketing_spend_total', 'marketing_allocated'], inplace=True, errors='ignore')


    # ---------------------------------------------------------
    # 2. AGRUPACIÓN MENSUAL (MONTH)
    # ---------------------------------------------------------
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

    # --- LÓGICA DE GROSS MARGIN 2 y 3 (MENSUAL) ---
    def get_qb_shipping_month(row):
        y = str(int(row['year']))
        m = str(row['month']).zfill(2)
        y_data = qb_summaries.get(y, qb_summaries.get(int(y), {}))
        return float(y_data.get(m, 0.0))

    shopify_by_brand_month['qb_shipping_total'] = shopify_by_brand_month.apply(get_qb_shipping_month, axis=1)
    monthly_totals = shopify_by_brand_month.groupby(['year', 'month'])['net_sales'].transform('sum')
    shopify_by_brand_month['sales_proportion'] = (shopify_by_brand_month['net_sales'] / monthly_totals.replace(0, pd.NA)).fillna(0)
    shopify_by_brand_month['qb_shipping_allocated'] = shopify_by_brand_month['qb_shipping_total'] * shopify_by_brand_month['sales_proportion']

    shopify_by_brand_month['applied_shipping'] = shopify_by_brand_month.apply(
        lambda x: x['qb_shipping_allocated'] if x['qb_shipping_total'] > 0 else x['shipping_charges'], axis=1
    )

    shopify_by_brand_month['gross_profit_2'] = shopify_by_brand_month['gross_profit_1'] - shopify_by_brand_month['applied_shipping']
    shopify_by_brand_month['gross_margin_2'] = (shopify_by_brand_month['gross_profit_2'] / shopify_by_brand_month['net_sales'].replace(0, pd.NA)).fillna(0)

    def get_marketing_month(row):
        y = str(int(row['year']))
        m = str(row['month']).zfill(2)
        y_data = marketing_summaries.get(y, marketing_summaries.get(int(y), {}))
        return float(y_data.get(m, 0.0))

    shopify_by_brand_month['marketing_spend_total'] = shopify_by_brand_month.apply(get_marketing_month, axis=1)
    shopify_by_brand_month['marketing_allocated'] = shopify_by_brand_month['marketing_spend_total'] * shopify_by_brand_month['sales_proportion']

    shopify_by_brand_month['gross_profit_3'] = shopify_by_brand_month['gross_profit_2'] - shopify_by_brand_month['marketing_allocated']
    shopify_by_brand_month['gross_margin_3'] = (shopify_by_brand_month['gross_profit_3'] / shopify_by_brand_month['net_sales'].replace(0, pd.NA)).fillna(0)

    # Limpieza de columnas temporales
    shopify_by_brand_month.drop(columns=['qb_shipping_total', 'sales_proportion', 'qb_shipping_allocated', 'applied_shipping', 'marketing_spend_total', 'marketing_allocated'], inplace=True, errors='ignore')


    # ---------------------------------------------------------
    # 3. AGRUPACIÓN POR CANAL
    # ---------------------------------------------------------
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
        "marketing_summary": marketing_summaries,
        "bill_rows": bill_rows,
    }

