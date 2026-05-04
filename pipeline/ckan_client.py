import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BASE_URL = os.getenv("CKAN_BASE_URL", "https://data.gov.hr/ckan/api/3/action")


class CKANClient:

    def __init__(self, base_url: str = BASE_URL, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout

    def get_all_datasets(self, rows_per_page: int = 100) -> list[dict]:
        """Paginate through ALL datasets on data.gov.hr."""
        all_datasets = []
        offset = 0

        while True:
            resp = requests.get(
                f"{self.base_url}/package_search",
                params={"rows": rows_per_page, "start": offset, "sort": "metadata_modified desc"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()["result"]
            batch = data["results"]
            all_datasets.extend(batch)
            logger.info("Fetched %d/%d datasets", len(all_datasets), data["count"])

            if offset + rows_per_page >= data["count"]:
                break
            offset += rows_per_page

        return all_datasets

    def get_dataset(self, name_or_id: str) -> dict:
        """Fetch a single dataset by CKAN name or ID."""
        resp = requests.get(
            f"{self.base_url}/package_show",
            params={"id": name_or_id},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["result"]

    def get_resource_data(self, resource_id: str, use_datastore: bool = True) -> list[dict]:
        """
        Fetch all records for a resource.
        Prefers datastore_search when available (no full-file download).
        Falls back to downloading the raw file.
        """
        if use_datastore:
            try:
                return self._datastore_search(resource_id)
            except Exception as e:
                logger.warning("datastore_search failed for %s: %s — falling back to file download", resource_id, e)
        return self._download_file(resource_id)

    def _datastore_search(self, resource_id: str, limit: int = 10000) -> list[dict]:
        """Query CKAN datastore directly — no full file download."""
        all_records = []
        offset = 0

        while True:
            resp = requests.get(
                f"{self.base_url}/datastore_search",
                params={"resource_id": resource_id, "limit": limit, "offset": offset},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            result = resp.json()["result"]
            all_records.extend(result["records"])
            logger.debug("datastore_search %s: fetched %d records", resource_id, len(all_records))

            if len(result["records"]) < limit:
                break
            offset += limit

        return all_records

    def _download_file(self, resource_id: str) -> list[dict]:
        """Download raw resource file and parse it (JSON or CSV)."""
        import io
        import json
        import pandas as pd

        # First get the resource URL
        resp = requests.get(
            f"{self.base_url}/resource_show",
            params={"id": resource_id},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        resource = resp.json()["result"]
        url = resource["url"]
        fmt = resource.get("format", "").upper()

        file_resp = requests.get(url, timeout=120)
        file_resp.raise_for_status()

        if fmt == "JSON" or url.endswith(".json"):
            data = file_resp.json()
            # Handle both list and {"data": [...]} shapes
            if isinstance(data, list):
                return data
            for key in ("data", "results", "records"):
                if key in data:
                    return data[key]
            return data
        else:
            # Default: try CSV
            df = pd.read_csv(io.StringIO(file_resp.text))
            return df.to_dict(orient="records")

    def is_healthy(self) -> bool:
        """Check if data.gov.hr CKAN API is reachable."""
        try:
            resp = requests.get(f"{self.base_url}/site_read", timeout=10)
            return resp.json().get("success", False)
        except Exception:
            return False
