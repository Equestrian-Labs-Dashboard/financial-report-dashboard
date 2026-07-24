import io
import logging
import os
import re

import pandas as pd
import requests

logger = logging.getLogger(__name__)

DEFAULT_SHEET_ID = "1ROTaII-_S_0VntYvOZj8GFCoUnkQVcr1rPES0p-14mI"
# Pestaña "Google Ads" indicada por el usuario.
DEFAULT_GOOGLE_ADS_GID = "413068087"
DEFAULT_START_YEAR = 2024


def _env_or_default(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


SHEET_ID = _env_or_default("MARKETING_SHEET_ID", DEFAULT_SHEET_ID)
# Acepta el nombre nuevo y también el secreto existente MARKETING_SHEET_GID.
GOOGLE_ADS_GID = _env_or_default(
    "MARKETING_GOOGLE_ADS_GID",
    _env_or_default("MARKETING_SHEET_GID", DEFAULT_GOOGLE_ADS_GID),
)
MARKETING_SHEET_START_YEAR = int(
    _env_or_default("MARKETING_SHEET_START_YEAR", str(DEFAULT_START_YEAR))
)

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def _empty_months() -> dict[str, float]:
    return {f"{month:02d}": 0.0 for month in range(1, 13)}


def _clean_column_name(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _money(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    clean = str(value).strip()
    if not clean or clean.lower() in {"nan", "none", "-"}:
        return 0.0
    negative = clean.startswith("(") and clean.endswith(")")
    clean = clean.replace("$", "").replace(",", "").replace("(", "").replace(")", "").strip()
    try:
        amount = float(clean)
        return -amount if negative else amount
    except ValueError:
        return 0.0


def _find_header_row(raw_df: pd.DataFrame) -> int:
    for row_index in range(min(len(raw_df), 40)):
        values = {_clean_column_name(value) for value in raw_df.iloc[row_index].tolist()}
        if "date" in values and "spend" in values:
            return row_index
    raise RuntimeError("Google Ads sheet does not contain a Date/Spend header row.")


def _read_sheet(sheet_id: str, gid: str) -> pd.DataFrame:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    response = requests.get(url, timeout=45)
    response.raise_for_status()
    raw_df = pd.read_csv(io.StringIO(response.text), header=None, dtype=str, keep_default_na=False)
    header_row = _find_header_row(raw_df)
    headers = [str(value).strip() for value in raw_df.iloc[header_row].tolist()]
    data = raw_df.iloc[header_row + 1:].copy()
    data.columns = headers
    data = data.loc[:, [column for column in data.columns if str(column).strip()]]
    return data.reset_index(drop=True)


def _build_year_month_spend(df: pd.DataFrame, start_year: int) -> dict[int, dict[str, float]]:
    normalized_columns = {_clean_column_name(column): column for column in df.columns}
    date_column = normalized_columns.get("date")
    spend_column = normalized_columns.get("spend")
    if not date_column or not spend_column:
        raise RuntimeError("Google Ads sheet must contain Date and Spend columns.")

    by_year: dict[int, dict[str, float]] = {}
    current_year = start_year
    previous_month = None

    for _, row in df.iterrows():
        date_label = str(row.get(date_column, "")).strip().lower().rstrip(".")
        month_number = MONTH_MAP.get(date_label)

        # Solo usa filas resumen mensuales (Jan, February, etc.).
        # Ignora las filas diarias como 7/1/2026, 7/2/2026, etc.
        if month_number is None:
            continue

        # Cuando vuelve a January/Jan comienza el bloque del año siguiente.
        if previous_month is not None and month_number <= previous_month:
            current_year += 1

        by_year.setdefault(current_year, _empty_months())
        by_year[current_year][f"{month_number:02d}"] = _money(row.get(spend_column, 0))
        previous_month = month_number

    return by_year


def get_marketing_spend(year: int, sheet_id: str | None = None, gid: str | None = None) -> dict[str, float]:
    """
    Devuelve el Spend mensual de la pestaña Google Ads para Corro.

    En este proyecto, Ads / Stats usa exclusivamente esta pestaña:
        Ads / Stats = Google Ads Spend

    Devuelve {"01": enero, ..., "12": diciembre}.
    """
    selected_sheet_id = (sheet_id or SHEET_ID).strip() or DEFAULT_SHEET_ID
    selected_gid = (gid or GOOGLE_ADS_GID).strip() or DEFAULT_GOOGLE_ADS_GID

    try:
        df = _read_sheet(selected_sheet_id, selected_gid)
        all_years = _build_year_month_spend(df, MARKETING_SHEET_START_YEAR)
        result = all_years.get(int(year), _empty_months())
        logger.info(
            "Corro Google Ads loaded for %s from gid=%s. Total: %.2f",
            year,
            selected_gid,
            sum(result.values()),
        )
        return result
    except Exception as exc:
        logger.exception("Unable to read Corro Google Ads spend for %s: %s", year, exc)
        return _empty_months()
