import json
import os
from datetime import datetime, timezone

import config
from extractors.shopify import get_shopify_rows, get_shopify_location_rows
from extractors.quickbooks import get_qb_shipping_costs
from extractors.google_sheets_marketing import get_marketing_spend
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
    marketing_summaries = {}

    for year in years:
        print(f"Processing financial year: {year}")

        for brand, credentials in config.SHOPIFY_STORES.items():
            try:
                print(f"Extracting Shopify data for {brand}...")
                rows = get_shopify_rows(
                    brand=brand,
                    store=credentials["store"],
                    token=credentials["token"],
                    year=year,
                )
                all_shopify_rows.extend(rows)
                print(f"{brand} Shopify rows: {len(rows)}")
            except Exception as exc:
                print(f"Shopify error for {brand} {year}: {exc}")

            # Wellington is a Corro POS/store split, not a warehouse split and not Cavali.
            if config.WELLINGTON_LOCATION_ID and brand == "Corro":
                try:
                    print(
                        f"Extracting Wellington POS/store data from Corro "
                        f"for location {config.WELLINGTON_LOCATION_ID}..."
                    )
                    wellington_rows = get_shopify_location_rows(
                        view_name=config.WELLINGTON_VIEW_NAME,
                        parent_brand=brand,
                        store=credentials["store"],
                        token=credentials["token"],
                        year=year,
                        location_id=str(config.WELLINGTON_LOCATION_ID),
                        location_name=str(config.WELLINGTON_LOCATION_NAME),
                    )
                    all_shopify_rows.extend(wellington_rows)
                    print(f"Corro Wellington rows: {len(wellington_rows)}")
                except Exception as exc:
                    print(f"Wellington POS/store error for Corro {year}: {exc}")

        if config.QB_CLIENT_ID and config.QB_CLIENT_SECRET and config.QB_REFRESH_TOKEN:
            try:
                print(f"Extracting QuickBooks shipping data for year {year}...")
                shipping_data = get_qb_shipping_costs(
                    client_id=config.QB_CLIENT_ID,
                    client_secret=config.QB_CLIENT_SECRET,
                    refresh_token=config.QB_REFRESH_TOKEN,
                    realm_id=config.QB_REALM_ID,
                    year=year,
                )
                qb_summaries[year] = shipping_data
                print(f"QuickBooks data extracted successfully for {year}.")
            except Exception as exc:
                print(f"QuickBooks error for year {year}: {exc}")
                qb_summaries[year] = {f"{m:02d}": 0.0 for m in range(1, 13)}
        else:
            print("QuickBooks credentials missing in config. Skipping API extraction.")
            qb_summaries[year] = {f"{m:02d}": 0.0 for m in range(1, 13)}

        try:
            print(f"Extracting marketing spend (Google+META) for year {year}...")
            marketing_summaries[year] = get_marketing_spend(year=year)
            print(f"Marketing spend extracted successfully for {year}.")
        except Exception as exc:
            print(f"Marketing spend error for year {year}: {exc}")
            marketing_summaries[year] = {f"{m:02d}": 0.0 for m in range(1, 13)}

        print("BILL skipped for now.")

    report = build_financial_report(
        shopify_rows=all_shopify_rows,
        bill_rows=all_bill_rows,
        qb_summaries=qb_summaries,
        marketing_summaries=marketing_summaries,
    )

    save_json(report, "docs/financial_report.json")
    print("Financial report completed successfully.")


if __name__ == "__main__":
    run()
