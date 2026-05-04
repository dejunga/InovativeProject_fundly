import logging
from sqlalchemy import text
from database import engine

logger = logging.getLogger(__name__)


def get_changed_datasets(ckan_datasets: list[dict]) -> dict:
    """
    Compare CKAN dataset list against what we have stored in dataset_registry.

    Returns:
        {
            "new":       [dataset, ...],    # never seen before
            "changed":   [dataset, ...],    # file_hash is different
            "deleted":   [ckan_id, ...],    # in DB but gone from CKAN
            "unchanged": [dataset, ...],    # hash matches, skip
        }
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT ckan_id, file_hash FROM dataset_registry WHERE status = 'active'")
        ).fetchall()

    stored_map = {row.ckan_id: row.file_hash for row in rows}
    ckan_ids_seen = set()
    result = {"new": [], "changed": [], "deleted": [], "unchanged": []}

    for dataset in ckan_datasets:
        ckan_id = dataset["id"]
        # CKAN puts hash on individual resources, not the package itself.
        # We use the package-level metadata_modified as a proxy when no explicit hash.
        ckan_hash = _extract_hash(dataset)
        ckan_ids_seen.add(ckan_id)

        if ckan_id not in stored_map:
            result["new"].append(dataset)
        elif stored_map[ckan_id] != ckan_hash:
            result["changed"].append(dataset)
        else:
            result["unchanged"].append(dataset)

    result["deleted"] = [
        ckan_id for ckan_id in stored_map if ckan_id not in ckan_ids_seen
    ]

    logger.info(
        "Change detection: %d new, %d changed, %d unchanged, %d deleted",
        len(result["new"]),
        len(result["changed"]),
        len(result["unchanged"]),
        len(result["deleted"]),
    )
    return result


def _extract_hash(dataset: dict) -> str:
    """
    Best-effort hash for a CKAN package.
    Prefer the first resource hash; fall back to metadata_modified.
    """
    for resource in dataset.get("resources", []):
        h = resource.get("hash", "")
        if h:
            return h
    return dataset.get("metadata_modified", "")
