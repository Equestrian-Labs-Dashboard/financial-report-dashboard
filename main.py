import json
import os
from datetime import datetime, timezone

import config
from extractors.shopify import get_orders, normalize_orders
from extractors.quickbooks import get_profit_and_loss, extract_qb_summary
from extractors.bill import get_invoices, normalize_invoices
from transforms.financial_report import build_financial_report


def save_json(data: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    print(f"Saved: {path}")


def run():
    current_year = datetime.now(timezone.utc).year
    years = range(config.START_YEAR, current_year + 1)

    all_transactions = []
    qb_summaries = {}

    for year in years:
        print(f"Processing financial year: {year}")

        try:
            shopify_orders = get_orders(year)
            shopify_rows = normalize_orders(shopify_orders, year)
            all_transactions.extend(shopify_rows)
            print(f"Shopify orders: {len(shopify_orders)}")
        except Exception as exc:
            print(f"Shopify error for {year}: {exc}")

        try:
            qb_report = get_profit_and_loss(year)
            qb_summaries[str(year)] = extract_qb_summary(qb_report, year)
            print("QuickBooks P&L: OK")
        except Exception as exc:
            print(f"QuickBooks error for {year}: {exc}")

        try:
            bill_invoices = get_invoices(year)
            bill_rows = normalize_invoices(bill_invoices, year)
            all_transactions.extend(bill_rows)
            print(f"BILL invoices: {len(bill_invoices)}")
        except Exception as exc:
            print(f"BILL error for {year}: {exc}")

    report = build_financial_report(all_transactions, qb_summaries)

    save_json(report, "docs/financial_report.json")

    print("Financial report completed successfully.")


if __name__ == "__main__":
    run()
