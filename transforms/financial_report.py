import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone
import pandas as pd

def build_financial_report(shopify_rows, bill_rows, qb_summaries):
    shopify_df = pd.DataFrame(shopify_rows)
    
    # 1. Limpieza básica que SIEMPRE funciona
    numeric_cols = ["total_sales", "gross_sales", "discounts", "returns", "net_sales", "cogs", "gross_profit_1", "shipping_charges", "transactions", "sessions_reached_checkout", "sessions_completed_checkout"]
    for col in numeric_cols:
        if col in shopify_df.columns:
            shopify_df[col] = pd.to_numeric(shopify_df[col], errors="coerce").fillna(0)
    
    shopify_df["year"] = pd.to_numeric(shopify_df["year"], errors="coerce").fillna(0).astype(int)
    shopify_df["month"] = shopify_df["month"].astype(str).str.zfill(2)

    # 2. Intentar cargar Marketing (Si falla, no pasa nada)
    marketing_dict = {}
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if creds_json:
        try:
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
            client = gspread.authorize(creds)
            sheet = client.open_by_key("1ROTaII-_S_0VntYvOZj8GFCoUnkQVcr1rPES0p-14mI").worksheet("Total Google+META")
            data = sheet.get_all_values()
            if len(data) > 1:
                df_ads = pd.DataFrame(data[1:], columns=data[0])
                df_ads['Spend'] = df_ads['Spend'].astype(str).replace({'\$': '', ',': ''}, regex=True)
                df_ads['Spend'] = pd.to_numeric(df_ads['Spend'], errors='coerce').fillna(0)
                df_ads['Date'] = pd.to_datetime(df_ads['Date'], errors='coerce')
                df_ads = df_ads.dropna(subset=['Date'])
                df_ads['year'] = df_ads['Date'].dt.year.astype(str)
                df_ads['month'] = df_ads['Date'].dt.month.astype(str).str.zfill(2)
                ads_grouped = df_ads.groupby(['year', 'month'])['Spend'].sum().reset_index()
                for _, row in ads_grouped.iterrows():
                    if row['year'] not in marketing_dict: marketing_dict[row['year']] = {}
                    marketing_dict[row['year']][row['month']] = float(row['Spend'])
        except Exception as e:
            print(f"Marketing falló (continuando sin él): {e}")

    # 3. Cálculos
    df = shopify_df.groupby(["brand", "year", "month"], as_index=False).sum()
    
    # GP2 / GM2 (QuickBooks) - Si QB falla, usamos 0 para no romper el reporte
    def get_qb(row): 
        try: return float(qb_summaries.get(str(row['year']), {}).get(row['month'], 0.0))
        except: return 0.0
    
    df['shipping_cost'] = df.apply(get_qb, axis=1)
    df['gross_profit_2'] = df['gross_profit_1'] - df['shipping_cost']
    df['gross_margin_2'] = (df['gross_profit_2'] / df['net_sales'].replace(0, pd.NA)).fillna(0)
    
    # GP3 / GM3 (Marketing)
    def get_mkt(row):
        try: return float(marketing_dict.get(str(row['year']), {}).get(row['month'], 0.0))
        except: return 0.0
        
    df['marketing_cost'] = df.apply(get_mkt, axis=1)
    df['gross_profit_3'] = df['gross_profit_2'] - df['marketing_cost']
    df['gross_margin_3'] = (df['gross_profit_3'] / df['net_sales'].replace(0, pd.NA)).fillna(0)

    # 4. Asegurar formato de retorno
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "shopify_kpis_by_brand_month": df.to_dict(orient="records"),
        "qb_summary": qb_summaries,
        "bill_rows": bill_rows,
    }
