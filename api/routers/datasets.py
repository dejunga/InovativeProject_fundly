from fastapi import APIRouter, Query
from sqlalchemy import text
from database import engine

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.get("")
def list_datasets(
    status: str | None = Query(None, description="Filter by status: active | deleted"),
):
    sql = """
        SELECT
            ckan_id,
            ckan_name,
            title,
            organization,
            file_hash,
            last_modified,
            last_synced_at,
            refresh_freq,
            row_count,
            status,
            deleted_at,
            created_at
        FROM dataset_registry
        {where}
        ORDER BY last_synced_at DESC NULLS LAST
    """
    where = "WHERE status = :status" if status else ""
    params = {"status": status} if status else {}

    with engine.connect() as conn:
        rows = conn.execute(text(sql.format(where=where)), params).mappings().all()

    return [dict(r) for r in rows]


@router.get("/{ckan_id}")
def get_dataset(ckan_id: str):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM dataset_registry WHERE ckan_id = :id"),
            {"id": ckan_id},
        ).mappings().first()

    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Dataset not found")

    return dict(row)
