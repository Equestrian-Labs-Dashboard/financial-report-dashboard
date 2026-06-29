import os
import logging
from intuitlib.client import AuthClient
from intuitlib.exceptions import AuthClientError
import requests

logger = logging.getLogger(__name__)

def get_qb_shipping_costs(year):
    """
    Extrae los costos de envío desde QuickBooks Online Sandbox utilizando
    OAuth 2.0 y las credenciales almacenadas en GitHub Secrets.
    """
    client_id = os.getenv("QB_CLIENT_ID")
    client_secret = os.getenv("QB_CLIENT_SECRET")
    refresh_token = os.getenv("QB_REFRESH_TOKEN")
    realm_id = os.getenv("QB_REALM_ID")

    if not all([client_id, client_secret, refresh_token, realm_id]):
        logger.error("Faltan credenciales de QuickBooks en las variables de entorno.")
        return 0

    # Inicializar el cliente de autenticación oficial apuntando a Sandbox
    auth_client = AuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl",
        environment="sandbox"
    )

    try:
        # Refrescar el token de acceso usando el Refresh Token de tus Secrets
        auth_client.refresh(refresh_token=refresh_token)
        access_token = auth_client.access_token
    except AuthClientError as e:
        logger.error(f"Error al refrescar el token de QuickBooks: {e.intuit_error_display_check_and_try_again}")
        return 0
    except Exception as e:
        logger.error(f"Error inesperado en la autenticación de QuickBooks: {e}")
        return 0

    # Configurar los headers para la consulta a la API
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Query para extraer los gastos de envío (Shipping) del año correspondiente
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    # Query estándar de QuickBooks para agrupar cuentas de gastos de envío
    query = f"SELECT TotalAmt FROM Purchase WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}'"
    url = f"https://sandbox-quickbooks.api.intuit.com/v3/company/{realm_id}/query?query={query}"

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Sumar los montos encontrados si existen registros
            purchases = data.get("QueryResponse", {}).get("Purchase", [])
            total_shipping = sum(float(p.get("TotalAmt", 0)) for p in purchases)
            logger.info(f"Datos de envío de QuickBooks para {year} extraídos con éxito.")
            return total_shipping
        elif response.status_code == 401:
            logger.error(f"Error API QB (401): Authorization Failure para el año {year}.")
            return 0
        else:
            logger.error(f"Error en la API de QuickBooks ({response.status_code}): {response.text}")
            return 0
    except Exception as e:
        logger.error(f"Error de conexión con la API de QuickBooks: {e}")
        return 0
