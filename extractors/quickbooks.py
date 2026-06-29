import os
import logging
import requests
from intuitlib.client import AuthClient
from intuitlib.exceptions import AuthClientError

logger = logging.getLogger(__name__)

def get_qb_shipping_costs(year, *args, **kwargs):
    """
    Extrae los costos de envío acumulados mensualmente desde QuickBooks Online Sandbox.
    Acepta cualquier argumento adicional (*args, **kwargs) enviado por main.py para evitar errores.
    """
    client_id = os.getenv("QB_CLIENT_ID")
    client_secret = os.getenv("QB_CLIENT_SECRET")
    refresh_token = os.getenv("QB_REFRESH_TOKEN")
    realm_id = os.getenv("QB_REALM_ID")

    # Inicializar el diccionario de meses vacío de '01' a '12'
    qb_monthly_shipping = {f"{m:02d}": 0.0 for m in range(1, 13)}

    if not all([client_id, client_secret, refresh_token, realm_id]):
        logger.error("Faltan credenciales de QuickBooks en las variables de entorno de GitHub.")
        return qb_monthly_shipping

    # AuthClient configurado correctamente para Sandbox
    auth_client = AuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl",
        environment="sandbox"
    )

    try:
        # Renovar el token usando el secreto guardado
        auth_client.refresh(refresh_token=refresh_token)
        access_token = auth_client.access_token
    except AuthClientError as e:
        logger.error(f"Error de autenticación en QB (Oauth): {e}")
        return qb_monthly_shipping
    except Exception as e:
        logger.error(f"Error inesperado al renovar token de QB: {e}")
        return qb_monthly_shipping

    url = f"https://sandbox-quickbooks.api.intuit.com/v3/company/{realm_id}/query"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "text/plain"
    }

    # Query SQL exacto para extraer transacciones del año correspondiente
    query = f"SELECT * FROM Purchase WHERE TxnDate >= '{year}-01-01' AND TxnDate <= '{year}-12-31'"

    try:
        response = requests.post(url, headers=headers, data=query)
        if response.status_code == 200:
            data = response.json()
            purchases = data.get("QueryResponse", {}).get("Purchase", [])
            
            for item in purchases:
                txn_date = item.get("TxnDate", "")
                if txn_date:
                    # Extraer el mes en formato '02', '03', etc.
                    month = txn_date.split("-")[1]
                    total_amt = float(item.get("TotalAmt", 0.0))
                    if month in qb_monthly_shipping:
                        qb_monthly_shipping[month] += total_amt
                        
            logger.info(f"Datos de envío de QuickBooks para {year} procesados exitosamente por mes.")
        elif response.status_code == 401:
            logger.error(f"Error API QB (401): Falla de autorización para el año {year}. Verifica el Refresh Token.")
        else:
            logger.error(f"Error API QB ({response.status_code}): {response.text}")
    except Exception as e:
        logger.error(f"Error de conexión al extraer datos de QuickBooks: {e}")

    return qb_monthly_shipping
