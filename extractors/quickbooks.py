import requests
from intuitlib.client import AuthClient

def get_qb_shipping_costs(client_id, client_secret, refresh_token, realm_id, year):
    """
    Se conecta a la API de QuickBooks en producción, renueva el token
    y extrae el costo acumulado mensual de envíos para el año consultado.
    """
    auth_client = AuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl",
        environment="production",
    )
    
    try:
        auth_client.refresh(refresh_token=refresh_token)
        access_token = auth_client.access_token
    except Exception as e:
        print(f"Error renovando el token de QuickBooks: {e}")
        return {}

    url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/query"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "text/plain"
    }

    # Consulta SQL a la API de QuickBooks para traer los registros de gastos de envío
    query = f"SELECT * FROM Purchase WHERE TxnDate >= '{year}-01-01' AND TxnDate <= '{year}-12-31'"
    qb_monthly_shipping = {f"{m:02d}": 0.0 for m in range(1, 13)}

    try:
        response = requests.post(url, headers=headers, data=query)
        if response.status_code == 200:
            data = response.json()
            purchases = data.get("QueryResponse", {}).get("Purchase", [])
            for item in purchases:
                txn_date = item.get("TxnDate", "")
                if txn_date:
                    month = txn_date.split("-")[1]
                    total_amt = float(item.get("TotalAmt", 0.0))
                    qb_monthly_shipping[month] += total_amt
        else:
            print(f"Error API QB ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"Error al extraer datos de QuickBooks: {e}")

    return qb_monthly_shipping
