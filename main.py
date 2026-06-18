import json
import os
from datetime import datetime, timezone

import config
from extractors.shopify import get_orders, normalize_shopify_orders
from transforms.financial_report import build_financial_report


def save_json(data: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    print(f"Saved: {path}")


def run():
    current_year = datetime.now(timezone.utc).year
    years = range(config.START_YEAR, current_year + 1)

    all_shopify_rows = []
    all_bill_rows = []
    qb_summaries = {}

    for year in years:
        print(f"Processing financial year: {year}")

        for brand, credentials in config.SHOPIFY_STORES.items():
            try:
                print(f"Extracting Shopify orders for {brand}...")

                orders = get_orders(
                    brand=brand,
                    store=credentials["store"],
                    token=credentials["token"],
                    year=year,
                )

                rows = normalize_shopify_orders(
                    brand=brand,
                    orders=orders,
                    year=year,
                )

                all_shopify_rows.extend(rows)

                print(f"{brand} Shopify orders: {len(orders)}")

            except Exception as exc:
                print(f"Shopify error for {brand} {year}: {exc}")

        print("QuickBooks skipped for now.")
        print("BILL skipped for now.")

    report = build_financial_report(
        shopify_rows=all_shopify_rows,
        bill_rows=all_bill_rows,
        qb_summaries=qb_summaries,
    )

    save_json(report, "docs/financial_report.json")

    print("Financial report completed successfully.")


if __name__ == "__main__":
    run()
