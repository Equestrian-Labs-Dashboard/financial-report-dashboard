from datetime import datetime, timezone
import pandas as pd


def build_financial_report(transaction_rows: list[dict], qb_summaries: dict) -> dict:
    df = pd.DataFrame(transaction_rows)

    if df.empty:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "years_available": [],
            "kpis_by_year": [],
            "by_channel_year": [],
            "by_month": [],
            "qb_summary": qb_summaries,
        }

    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce").fillna(0)
    df["subtotal"] = pd.to_numeric(df["subtotal"], errors="coerce").fillna(0)
    df["tax"] = pd.to_numeric(df["tax"], errors="coerce").fillna(0)
    df["discounts"] = pd.to_numeric(df["discounts"], errors="coerce").fillna(0)
    df["transactions"] = pd.to_numeric(df["transactions"], errors="coerce").fillna(1)
    df["year"] = df["year"].astype(int)
    df["month"] = df["month"].astype(str).str.zfill(2)

    by_channel_year = (
        df.groupby(["year", "channel"], as_index=False)
        .agg(
            total_revenue=("revenue", "sum"),
            subtotal=("subtotal", "sum"),
            tax=("tax", "sum"),
            discounts=("discounts", "sum"),
            transactions=("transactions", "sum"),
        )
    )

    by_month = (
        df.groupby(["year", "month", "channel"], as_index=False)
        .agg(
            total_revenue=("revenue", "sum"),
            transactions=("transactions", "sum"),
        )
    )

    kpis_by_year = (
        df.groupby(["year"], as_index=False)
        .agg(
            total_revenue=("revenue", "sum"),
            subtotal=("subtotal", "sum"),
            tax=("tax", "sum"),
            discounts=("discounts", "sum"),
            transactions=("transactions", "sum"),
        )
    )

    kpis_by_year["average_order_value"] = (
        kpis_by_year["total_revenue"] / kpis_by_year["transactions"]
    ).fillna(0)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "years_available": sorted(df["year"].unique().tolist()),
        "kpis_by_year": kpis_by_year.to_dict(orient="records"),
        "by_channel_year": by_channel_year.to_dict(orient="records"),
        "by_month": by_month.to_dict(orient="records"),
        "qb_summary": qb_summaries,
    }
