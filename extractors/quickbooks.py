import os
import logging
import requests
import urllib.parse
from intuitlib.client import AuthClient

logger = logging.getLogger(__name__)

def get_qb_shipping_costs(year, *args, **kwargs):
    """
    Extrae los costos de envío acumulados mensualmente desde QuickBooks Online Sandbox
    usando el método GET oficial con query param codificado.
    """
    qb_monthly_shipping = {f"{m:02d}": 0.0 for m in range(1, 13)}

    client_id = os.getenv("QB_CLIENT_ID")
    client_secret = os.getenv("QB_CLIENT_SECRET")
    refresh_token = os.getenv("QB_REFRESH_TOKEN")
    realm_id = os.getenv("QB_REALM_ID")

    if not all([client_id, client_secret, refresh_token, realm_id]):
        logger.error("Faltan credenciales de QuickBooks en las variables de entorno.")
        return qb_monthly_shipping

    auth_client = AuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl",
        environment="sandbox"
    )

    try:
        auth_client.refresh(refresh_token=refresh_token)
        access_token = auth_client.access_token
    except Exception as e:
        logger.error(f"Error de autenticación en QB al renovar token: {e}")
        return qb_monthly_shipping

    # 1. Definir la consulta SQL limpia
    query = f"SELECT * FROM Purchase WHERE TxnDate >= '{year}-01-01' AND TxnDate <= '{year}-12-31'"
    
    # 2. Codificar la consulta para que QuickBooks la entienda sin errores (Solución al 400)
    safe_query = urllib.parse.quote(query)
    
    # 3. Armar la URL oficial con el método GET
    url = f"https://sandbox-quickbooks.api.intuit.com/v3/company/{realm_id}/query?query={safe_query}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            purchases = data.get("QueryResponse", {}).get("Purchase", [])
            
            for item in purchases:
                txn_date = item.get("TxnDate", "")
                if txn_date:
                    month = txn_date.split("-")[1]
                    total_amt = float(item.get("TotalAmt", 0.0))
                    if month in qb_monthly_shipping:
                        qb_monthly_shipping[month] += total_amt
                        
            logger.info(f"Datos de envío de QuickBooks para {year} procesados exitosamente.")
        else:
            logger.error(f"Error API QB ({response.status_code}): {response.text}")
    except Exception as e:
        logger.error(f"Error de conexión al extraer datos de QuickBooks: {e}")

    return qb_monthly_shipping
