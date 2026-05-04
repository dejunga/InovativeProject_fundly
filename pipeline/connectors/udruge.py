import json
import logging

import pandas as pd

from .base import BaseConnector

logger = logging.getLogger(__name__)

DATASET_NAME = "registar-udruga"

# Resource name suffix that contains the main NGO records
CTS_RESOURCE_NAME = "Registar udruga Republike Hrvatske - CTS"
CTS_FORMAT = "JSON"


class UdrugeConnector(BaseConnector):
    dataset_name = DATASET_NAME
    target_table = "udruge"
    primary_key = "id"

    def get_resource_id(self, dataset: dict) -> str | None:
        """Return the CTS JSON resource ID (main NGO data)."""
        for r in dataset.get("resources", []):
            if r.get("name", "") == CTS_RESOURCE_NAME and r.get("format", "").upper() == CTS_FORMAT:
                return r["id"]
        # Fallback: first JSON resource
        for r in dataset.get("resources", []):
            if r.get("format", "").upper() == "JSON" and r.get("name", "") != "Registar udruga Republike Hrvatske - Djelatnosti":
                return r["id"]
        return None

    def datastore_active(self, dataset: dict) -> bool:
        """CTS resource is not in datastore — we download the JSON file."""
        return False

    def transform(self, raw_records: list[dict]) -> pd.DataFrame:
        if not raw_records:
            return pd.DataFrame()

        df = pd.DataFrame(raw_records)

        # Map CTS field names → our schema
        rename_map = {
            "UDR_ID":          "id",
            "NAZIV":           "naziv",
            "SKRACENI_NAZIV":  "skraceni_naziv",
            "OIB":             "oib",
            "ZUPANIJA":        "zupanija",
            "SJEDISTE":        "adresa",      # SJEDISTE = seat/address
            "DATUM_UPISA":     "datum_osnivanja",
            "DATUM_STATUSA":   "datum_brisanja",
        }
        df = df.rename(columns=rename_map)

        # id must be a string (our PK is TEXT)
        df["id"] = df["id"].astype(str)

        # Combine remaining rich fields into djelatnosti JSONB
        detail_cols = [
            "CILJEVI", "CILJANE_SKUPINE", "OPIS_DJELATNOSTI",
            "GOSPODARSKE_DJELATNOSTI", "OBLIK_UDRUZIVANJA",
            "NAZIV_NA_DRUGIM_JEZICIMA", "SKR_NAZIV_NA_DRUGIM_JEZICIMA",
            "DATUM_OSNIVACKE_SKUPSTINE", "REGISTARSKI_BROJ",
            "MAIL", "WEB_STRANICA", "STATUS",
        ]
        existing_detail = [c for c in detail_cols if c in df.columns]
        df["djelatnosti"] = df[existing_detail].apply(
            lambda row: json.dumps(
                {k: v for k, v in row.items() if v is not None and v == v},  # skip NaN
                ensure_ascii=False,
            ),
            axis=1,
        )

        # Parse dates
        for date_col in ["datum_osnivanja", "datum_brisanja"]:
            if date_col in df.columns:
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.date

        # Normalise county names
        df["zupanija"] = df["zupanija"].astype(str).str.strip().str.title().replace("Nan", None)

        # Ensure all target columns exist
        target_cols = ["id", "naziv", "skraceni_naziv", "oib", "zupanija",
                       "adresa", "datum_osnivanja", "datum_brisanja", "djelatnosti"]
        for col in target_cols:
            if col not in df.columns:
                df[col] = None

        return df[target_cols].where(pd.notna(df[target_cols]), None)
