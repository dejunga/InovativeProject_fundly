from abc import ABC, abstractmethod
import pandas as pd


class BaseConnector(ABC):
    dataset_name: str   # CKAN dataset name slug (used to find the package)
    target_table: str   # PostgreSQL table
    primary_key: str    # Column used for ON CONFLICT

    @abstractmethod
    def transform(self, raw_records: list[dict]) -> pd.DataFrame:
        """Normalize raw CKAN records into the target schema."""
        pass

    def get_resource_id(self, dataset: dict) -> str | None:
        """Return the first resource ID from a CKAN package dict."""
        resources = dataset.get("resources", [])
        if not resources:
            return None
        return resources[0]["id"]

    def datastore_active(self, dataset: dict) -> bool:
        resources = dataset.get("resources", [])
        if not resources:
            return False
        return bool(resources[0].get("datastore_active", False))
