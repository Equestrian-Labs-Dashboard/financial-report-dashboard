import logging
import io
import os
import requests
import pandas as pd
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SHEET_ID = os.getenv("MARKETING_SHEET_ID", "1ROTaII-_S_0VntYvOZj8GFCoUnkQVcr1rPES0p-14mI")
GID_TOTAL_GOOGLE_META = os.getenv("MARKETING_SHEET_GID", "901455843")

MONTH_MAP = {
    "January": "01", "February": "02", "March": "03", "April": "04",
    "May": "05", "June": "06", "July": "07", "August": "08",
    "September": "09", "October": "10", "Oct": "10",
    "November": "11", "Nov": "11", "December": "12", "Dec": "12",
}


def get_marketing_spend(year: int, sheet_id: str = SHEET_ID, gid: str = GID_TOTAL_GOOGLE_META) -> dict:
    """
    Lee el Spend mensual (Google+META combinado) desde un Google Sheet
    público de solo lectura. No requiere API key ni service account.
    Devuelve: {"01": spend, "02": spend, ...}
    """
    monthly_spend = {f"{m:02d}": 0.0 for m in range(1, 13)}

    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            logger.error(f"Error leyendo Google Sheet ({response.status_code})")
            return monthly_spend
        df = pd.read_csv(io.StringIO(response.text))
    except Exception as exc:
        logger.error(f"Error de conexión/parseo al leer Google Sheet: {exc}")
        return monthly_spend

    df = df.dropna(subset=["Date"]).reset_index(drop=True)
    df = df[df["Date"].isin(MONTH_MAP.keys())].reset_index(drop=True)

    # Cada vez que aparece "January" arranca un bloque/año nuevo.
    # No asumimos un año fijo: detectamos cuántos bloques hay y
    # asumimos que el ÚLTIMO bloque corresponde al año más reciente
    # con datos (el actual), y los anteriores van hacia atrás.
    block_starts = df.index[df["Date"] == "January"].tolist()
    if not block_starts:
        logger.warning("No se encontraron bloques 'January' en la hoja de marketing.")
        return monthly_spend

    num_blocks = len(block_starts)
    current_year = datetime.now(timezone.utc).year
    latest_year_in_sheet = current_year  # el último bloque = año más reciente
    block_index = year - (latest_year_in_sheet - (num_blocks - 1))

    if block_index < 0 or block_index >= num_blocks:
        logger.warning(f"Año {year} fuera de rango de la hoja de marketing ({num_blocks} bloques detectados).")
        return monthly_spend

    start_row = block_starts[block_index]
    end_row = start_row + 12
    year_block = df.iloc[start_row:end_row]

    if year_block.empty:
        logger.warning(f"Sin filas para el año {year} en la hoja de marketing.")
        return monthly_spend

    for _, row in year_block.iterrows():
        month_num = MONTH_MAP.get(row["Date"])
        if not month_num:
            continue
        spend_clean = str(row.get("Spend", "0")).replace("$", "").replace(",", "").strip()
        try:
            monthly_spend[month_num] = float(spend_clean)
        except ValueError:
            monthly_spend[month_num] = 0.0

    logger.info(f"Spend de marketing extraído para {year}.")
    return monthly_spend
