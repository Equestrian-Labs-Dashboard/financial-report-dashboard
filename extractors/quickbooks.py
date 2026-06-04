import base64
import requests
import config


def get_access_token() -> str:
    credentials = f"{config.QB_CLIENT_ID}:{config.QB_CLIENT_SECRET}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    response = requests.post(
        "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
        headers={
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": config.QB_REFRESH_TOKEN,
        },
        timeout=45,
    )

    response.raise_for_status()
    return response.json()["access_token"]


def get_profit_and_loss(year: int) -> dict:
    token = get_access_token()

    url = (
        f"https://quickbooks.api.intuit.com/v3/company/"
        f"{config.QB_REALM_ID}/reports/ProfitAndLoss"
    )

    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        params={
            "start_date": f"{year}-01-01",
            "end_date": f"{year}-12-31",
            "accounting_method": "Accrual",
        },
        timeout=45,
    )

    response.raise_for_status()
    return response.json()


def extract_qb_summary(report: dict, year: int) -> dict:
    values = {}

    def walk(node: dict):
        rows = node.get("Rows", {}).get("Row", [])

        for row in rows:
            if row.get("type") == "Data":
                columns = row.get("ColData", [])

                if len(columns) >= 2:
                    name = columns[0].get("value", "")
                    value = columns[1].get("value", "0").replace(",", "")
                    values[name] = value

            if "Rows" in row:
                walk(row)

    walk(report)

    def money(name: str) -> float:
        try:
            return float(values.get(name, 0) or 0)
        except ValueError:
            return 0.0

    total_income = money("Total Income")
    gross_profit = money("Gross Profit")
    net_income = money("Net Income")
    total_expenses = money("Total Expenses")
    total_cogs = money("Total Cost of Goods Sold")

    gross_margin = gross_profit / total_income if total_income else 0
    net_margin = net_income / total_income if total_income else 0

    return {
        "year": year,
        "source": "QuickBooks",
        "total_income": total_income,
        "total_cogs": total_cogs,
        "gross_profit": gross_profit,
        "total_expenses": total_expenses,
        "net_income": net_income,
        "gross_margin": gross_margin,
        "net_margin": net_margin,
    }
