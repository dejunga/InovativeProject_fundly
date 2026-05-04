"""
Main pipeline entry point.

Usage:
    python -m pipeline.orchestrator          # runs once
    python -m pipeline.orchestrator --run-once
"""

import logging
import sys
from datetime import datetime, timezone

from pipeline.ckan_client import CKANClient
from pipeline.change_detector import get_changed_datasets, _extract_hash
from pipeline.loader import (
    upsert_rows,
    soft_delete_missing,
    upsert_dataset_registry,
    mark_datasets_deleted,
    log_pipeline_run,
)
from pipeline.connectors.udruge import UdrugeConnector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Map CKAN dataset names → connector instances
CONNECTORS = {
    UdrugeConnector.dataset_name: UdrugeConnector(),
}


def run(run_type: str = "manual"):
    started_at = datetime.now(timezone.utc)
    stats = {
        "run_type": run_type,
        "started_at": started_at,
        "finished_at": None,
        "status": "failed",
        "datasets_checked": 0,
        "datasets_changed": 0,
        "datasets_unchanged": 0,
        "rows_inserted": 0,
        "rows_updated": 0,
        "rows_soft_deleted": 0,
        "error_message": None,
    }

    client = CKANClient()

    try:
        # 1. Check source health
        if not client.is_healthy():
            raise RuntimeError("data.gov.hr CKAN API is unreachable")

        # 2. Fetch all datasets from CKAN
        logger.info("Fetching dataset list from CKAN…")
        all_datasets = client.get_all_datasets()
        stats["datasets_checked"] = len(all_datasets)

        # 3. Detect what changed
        changes = get_changed_datasets(all_datasets)
        stats["datasets_changed"] = len(changes["new"]) + len(changes["changed"])
        stats["datasets_unchanged"] = len(changes["unchanged"])

        # 4. Mark deleted datasets in registry
        mark_datasets_deleted(changes["deleted"])

        # 5. Process new and changed datasets
        for dataset in changes["new"] + changes["changed"]:
            name = dataset.get("name", "")
            connector = CONNECTORS.get(name)
            if connector is None:
                # Dataset not handled yet — just register it
                file_hash = _extract_hash(dataset)
                upsert_dataset_registry(dataset, file_hash, row_count=0)
                continue

            logger.info("Processing dataset: %s", name)
            resource_id = connector.get_resource_id(dataset)
            if not resource_id:
                logger.warning("No resource found for %s, skipping", name)
                continue

            use_datastore = connector.datastore_active(dataset)
            raw_records = client.get_resource_data(resource_id, use_datastore=use_datastore)
            df = connector.transform(raw_records)

            inserted, updated = upsert_rows(df, connector.target_table, connector.primary_key)
            soft_deleted = soft_delete_missing(
                connector.target_table, connector.primary_key, df[connector.primary_key].tolist()
            )

            stats["rows_inserted"] += inserted
            stats["rows_updated"] += updated
            stats["rows_soft_deleted"] += soft_deleted

            file_hash = _extract_hash(dataset)
            upsert_dataset_registry(dataset, file_hash, row_count=len(df))

        stats["status"] = "success"
        logger.info("Pipeline finished successfully. Stats: %s", stats)

    except Exception as exc:
        stats["status"] = "failed"
        stats["error_message"] = str(exc)
        logger.exception("Pipeline failed: %s", exc)

    finally:
        stats["finished_at"] = datetime.now(timezone.utc)
        run_id = log_pipeline_run(stats)
        logger.info("Run logged as %s (status=%s)", run_id, stats["status"])

    return stats


def check_source_health():
    client = CKANClient()
    healthy = client.is_healthy()
    logger.info("CKAN health check: %s", "OK" if healthy else "UNREACHABLE")
    return healthy


if __name__ == "__main__":
    run(run_type="manual")
