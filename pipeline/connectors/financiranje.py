"""
Connector for 'Podaci o financiranju udruga' (Ured za udruge).

Downloads multiple Excel files (state / county / city / municipality level),
parses all yearly sheets, normalises into a single financijske_potpore table.
Linkable to udruge via OIB.

Sources:
  - data.gov.hr direct Excel files: 2004-2016
  - udruge.gov.hr ZIP archives:     2017-2019
"""

import hashlib
import io
import logging
import zipfile
from datetime import datetime, timezone

import pandas as pd
import requests
from psycopg2.extras import execute_values
from database import engine

logger = logging.getLogger(__name__)

DATASET_CKAN_ID = "podaci-o-financiranju-udruga"

# ── Direct Excel sources (2004-2016) ─────────────────────────────────────────
SOURCES = [
    {
        "url": "https://udruge.gov.hr/UserDocsImages/dokumenti/open_data_TDU_Odobrene%20financijske%20potpore%20od%202004.xlsx",
        "razina": "drzava",
    },
    {
        "url": "https://udruge.gov.hr/UserDocsImages/dokumenti/open_data_zupanije.xlsx",
        "razina": "zupanija",
    },
    {
        "url": "https://udruge.gov.hr/UserDocsImages/dokumenti/open_data_gradovi.xlsx",
        "razina": "grad",
    },
    {
        "url": "https://udruge.gov.hr/UserDocsImages/dokumenti/open_data_opcine.xlsx",
        "razina": "opcina",
    },
]

# ── ZIP archive sources (2017-2019) from udruge.gov.hr ───────────────────────
# Each ZIP contains one Excel with multiple sheets; sheet name → razina
_SHEET_RAZINA = {
    "tdu":          "drzava",
    "grad zagreb":  "grad",
    "zupanije":     "zupanija",
    "\u017eupanije": "zupanija",
    "gradovi":      "grad",
    "op\u0107ine":  "opcina",
    "opcine":       "opcina",
    # other grantors — included as-is with razina "ostalo"
    "javna trgova\u010dka dru\u0161tva": "ostalo",
    "turisti\u010dke zajednice":         "ostalo",
    "sportske zajednice":                "ostalo",
    "vatrogasne zajednice":              "ostalo",
    "zajednice tehni\u010dke kulture":   "ostalo",
    "zajednice teh. kulture":            "ostalo",
}

ZIP_SOURCES = [
    {
        "url": "https://udruge.gov.hr/UserDocsImages//dokumenti//Izvje%C5%A1%C4%87e%20za%202018.%20godinu%2C%20sa%20svim%20prilozima.zip",
        "excel_hint": "prilog 3",   # filename substring to pick the right Excel inside the ZIP
    },
    {
        "url": "https://udruge.gov.hr/UserDocsImages//dokumenti/Izvje%C5%A1%C4%87e%20o%20financiranju%202019//Izvjesce%20o%20financiranju%202019.zip",
        "excel_hint": "prilog 2 popis",
    },
]

# ── Column rename map ─────────────────────────────────────────────────────────
RENAME = {
    # New format (uppercase)
    "ORGANIZACIJA":                       "organizacija",
    "OIB":                                "oib",
    "PROJEKT":                            "projekt",
    "DAVATELJ":                           "davatelj",
    "GODINA":                             "godina",
    "IZNOS":                              "iznos",
    "ISPLA\u010cENI IZNOS":               "iznos",   # 2019
    "ISPLA\ufffdENI IZNOS":               "iznos",   # 2019 mojibake variant
    "\ufffdUPANIJA PROVEDBE PROJEKTA":    "zupanija_provedbe",
    "ZUPANIJA PROVEDBE PROJEKTA":         "zupanija_provedbe",
    "\u017dUPANIJA PROVEDBE PROJEKTA":    "zupanija_provedbe",
    # Old format (title case)
    "Organizacija":                       "organizacija",
    "Davatelj financijskih sredstava":    "davatelj",
    "Godina":                             "godina",
    "Iznos":                              "iznos",
    "Projekt":                            "projekt",
    "\ufffdupanija":                      "zupanija_provedbe",
    "Zupanija":                           "zupanija_provedbe",
    "\u017dupanija":                      "zupanija_provedbe",
}


def _fix_col(name: str) -> str:
    s = str(name).strip().rstrip()
    return RENAME.get(s, s)


def _parse_iznos(val) -> float | None:
    if val is None or (isinstance(val, float) and val != val):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s.upper() in ("N/P", "NP", "N/A", "-"):
        return None
    s = s.replace("Kn", "").replace("kn", "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _clean_oib(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip().split()[0]
    s = s.replace(".", "").replace(",", "")
    try:
        n = str(int(float(s)))
        return n if 8 <= len(n) <= 13 else None
    except (ValueError, OverflowError):
        return None


def _row_hash(row: pd.Series) -> str:
    return hashlib.md5(str(row.values).encode()).hexdigest()


def _sheet_to_razina(sheet_name: str) -> str:
    """Map an Excel sheet name to a razina value."""
    key = sheet_name.lower().strip()
    return _SHEET_RAZINA.get(key, "ostalo")


def _normalise_df(df: pd.DataFrame, razina: str) -> pd.DataFrame | None:
    """Apply column renaming, type coercions, and filter to required columns."""
    df = df.copy()
    df.columns = [_fix_col(str(c)) for c in df.columns]

    if "organizacija" not in df.columns:
        return None

    df = df.dropna(subset=["organizacija"])
    if df.empty:
        return None

    for col in ["oib", "projekt", "davatelj", "zupanija_provedbe", "godina", "iznos"]:
        if col not in df.columns:
            df[col] = None

    df["razina"] = razina
    df["oib"] = df["oib"].apply(_clean_oib)
    df["godina"] = pd.to_numeric(df["godina"], errors="coerce").astype("Int64")
    df["iznos"] = df["iznos"].apply(_parse_iznos)

    return df[["organizacija", "oib", "projekt", "davatelj",
               "razina", "zupanija_provedbe", "godina", "iznos"]]


def _find_header_row(ws_rows: list[list]) -> int:
    """Return 0-based index of the row containing real column headers."""
    for i, row in enumerate(ws_rows[:6]):
        row_strs = [str(c).strip().lower() if c is not None else "" for c in row]
        if any(k in row_strs for k in ("organizacija", "davatelj", "oib")):
            return i
    return 0


def fetch_and_parse() -> pd.DataFrame:
    frames = []

    # ── 2004-2016: direct Excel files ───────────────────────────────────────
    for source in SOURCES:
        url = source["url"]
        razina = source["razina"]
        logger.info("Downloading %s (%s)…", url.split("/")[-1], razina)
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
        except Exception as e:
            logger.warning("Failed to download %s: %s", url, e)
            continue

        try:
            xls = pd.ExcelFile(io.BytesIO(r.content), engine="openpyxl")
        except Exception as e:
            logger.warning("Failed to parse Excel from %s: %s", url, e)
            continue

        for sheet in xls.sheet_names:
            try:
                df = xls.parse(sheet, dtype=str)
                if df.empty:
                    continue
                normed = _normalise_df(df, razina)
                if normed is not None and not normed.empty:
                    frames.append(normed)
            except Exception as e:
                logger.warning("Error parsing sheet %s from %s: %s", sheet, url, e)

    # ── 2017-2019: ZIP archives with multi-sheet Excel ───────────────────────
    for source in ZIP_SOURCES:
        url = source["url"]
        hint = source.get("excel_hint", "").lower()
        logger.info("Downloading ZIP: %s…", url.split("/")[-1].split("%")[-1][:40])
        try:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
        except Exception as e:
            logger.warning("Failed to download ZIP %s: %s", url, e)
            continue

        try:
            zf = zipfile.ZipFile(io.BytesIO(r.content))
        except Exception as e:
            logger.warning("Failed to open ZIP from %s: %s", url, e)
            continue

        # Pick the right Excel file inside the ZIP
        xlsx_names = [n for n in zf.namelist() if n.lower().endswith((".xlsx", ".xls"))]
        target = next(
            (n for n in xlsx_names if hint and hint in n.lower()),
            xlsx_names[0] if xlsx_names else None,
        )
        if not target:
            logger.warning("No Excel file found in ZIP %s", url)
            continue

        logger.info("  Parsing %s", target.split("/")[-1])
        try:
            with zf.open(target) as f:
                xls = pd.ExcelFile(io.BytesIO(f.read()), engine="openpyxl")
        except Exception as e:
            logger.warning("Failed to parse Excel %s from ZIP: %s", target, e)
            continue

        for sheet in xls.sheet_names:
            razina = _sheet_to_razina(sheet)
            try:
                # Read without header first to find the actual header row
                raw = xls.parse(sheet, header=None, dtype=str)
                if raw.empty:
                    continue

                header_idx = _find_header_row(raw.values.tolist())
                df = xls.parse(sheet, header=header_idx, dtype=str)
                if df.empty:
                    continue

                normed = _normalise_df(df, razina)
                if normed is not None and not normed.empty:
                    frames.append(normed)
                    logger.info("    Sheet '%s' (%s): %d rows", sheet, razina, len(normed))
            except Exception as e:
                logger.warning("Error parsing sheet %s: %s", sheet, e)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    logger.info("Total rows fetched: %d", len(combined))
    return combined


def load(df: pd.DataFrame) -> tuple[int, int]:
    """
    Truncate-and-reload strategy.
    Returns (rows_inserted, rows_updated=0).
    """
    if df.empty:
        return 0, 0

    df = df.copy()
    df["row_hash"] = df.apply(_row_hash, axis=1)
    df["updated_at"] = datetime.now(timezone.utc)

    columns = ["organizacija", "oib", "projekt", "davatelj", "razina",
               "zupanija_provedbe", "godina", "iznos", "row_hash", "updated_at"]

    records = []
    for _, row in df[columns].iterrows():
        record = []
        for val in row:
            if hasattr(val, "item"):
                val = val.item()
            if val != val:
                val = None
            record.append(val)
        records.append(record)

    upsert_sql = f"""
        INSERT INTO financijske_potpore ({', '.join(columns)})
        VALUES %s
        ON CONFLICT DO NOTHING
    """

    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        cursor.execute("TRUNCATE TABLE financijske_potpore RESTART IDENTITY")
        execute_values(cursor, upsert_sql, records, page_size=1000)
        raw_conn.commit()
    finally:
        raw_conn.close()

    logger.info("Loaded %d rows into financijske_potpore", len(records))
    return len(records), 0


def run() -> tuple[int, int]:
    df = fetch_and_parse()
    return load(df)
