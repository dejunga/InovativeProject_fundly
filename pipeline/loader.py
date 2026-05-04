import hashlib
import json
import logging
from datetime import datetime, timezone

import pandas as pd
from psycopg2.extras import execute_values
from sqlalchemy import text
from database import engine

logger = logging.getLogger(__name__)


def _row_hash(row: pd.Series) -> str:
    return hashlib.md5(str(row.values).encode()).hexdigest()


def upsert_rows(df: pd.DataFrame, table: str, pk_column: str) -> tuple[int, int]:
    """
    Upsert rows into target table using row-level hash comparison.
    Returns (rows_inserted, rows_updated).
    """
    if df.empty:
        return 0, 0

    df = df.copy()
    df["row_hash"] = df.apply(_row_hash, axis=1)
    df["updated_at"] = datetime.now(timezone.utc)

    columns = list(df.columns)
    # Exclude updated_at from auto-SET since we set it explicitly to now()
    non_pk_cols = [c for c in columns if c not in (pk_column, "updated_at")]

    upsert_sql = f"""
        INSERT INTO {table} ({', '.join(columns)})
        VALUES %s
        ON CONFLICT ({pk_column})
        DO UPDATE SET
            {', '.join(f'{col} = EXCLUDED.{col}' for col in non_pk_cols)},
            updated_at = now()
        WHERE {table}.row_hash IS DISTINCT FROM EXCLUDED.row_hash
    """

    # Convert JSONB columns (lists/dicts) to JSON strings for psycopg2
    records = []
    for _, row in df.iterrows():
        record = []
        for val in row:
            if isinstance(val, (dict, list)):
                val = json.dumps(val)
            record.append(val)
        records.append(record)

    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        # Count rows before to estimate inserts vs updates
        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {pk_column} = ANY(%s)", (df[pk_column].tolist(),))
        existing_count = cursor.fetchone()[0]

        execute_values(cursor, upsert_sql, records)
        affected = cursor.rowcount
        raw_conn.commit()
    finally:
        raw_conn.close()

    # Rough split: new rows vs updated rows
    rows_inserted = max(0, len(df) - existing_count)
    rows_updated = max(0, affected - rows_inserted)
    logger.info("Upserted into %s: %d inserted, %d updated", table, rows_inserted, rows_updated)
    return rows_inserted, rows_updated


def soft_delete_missing(table: str, pk_column: str, active_ids: list) -> int:
    """
    Mark rows that are no longer in the source as deleted (soft delete).
    Never hard-deletes. Returns count of rows soft-deleted.
    """
    if not active_ids:
        return 0

    with engine.connect() as conn:
        result = conn.execute(
            text(f"""
                UPDATE {table}
                SET deleted_at = now()
                WHERE {pk_column} NOT IN :active_ids
                AND deleted_at IS NULL
            """),
            {"active_ids": tuple(active_ids)},
        )
        conn.commit()
        count = result.rowcount

    if count:
        logger.info("Soft-deleted %d rows from %s", count, table)
    return count


def upsert_dataset_registry(dataset: dict, file_hash: str, row_count: int):
    """Insert or update a dataset_registry record after a successful sync."""
    sql = text("""
        INSERT INTO dataset_registry (ckan_id, ckan_name, title, organization, file_hash,
                                      last_modified, last_synced_at, row_count, status)
        VALUES (:ckan_id, :ckan_name, :title, :organization, :file_hash,
                :last_modified, now(), :row_count, 'active')
        ON CONFLICT (ckan_id) DO UPDATE SET
            ckan_name      = EXCLUDED.ckan_name,
            title          = EXCLUDED.title,
            organization   = EXCLUDED.organization,
            file_hash      = EXCLUDED.file_hash,
            last_modified  = EXCLUDED.last_modified,
            last_synced_at = now(),
            row_count      = EXCLUDED.row_count,
            status         = 'active',
            deleted_at     = NULL
    """)

    org = dataset.get("organization") or {}
    with engine.connect() as conn:
        conn.execute(sql, {
            "ckan_id": dataset["id"],
            "ckan_name": dataset.get("name", ""),
            "title": dataset.get("title", ""),
            "organization": org.get("title") if isinstance(org, dict) else None,
            "file_hash": file_hash,
            "last_modified": dataset.get("metadata_modified"),
            "row_count": row_count,
        })
        conn.commit()


def mark_datasets_deleted(ckan_ids: list[str]):
    """Soft-delete dataset_registry entries that disappeared from CKAN."""
    if not ckan_ids:
        return
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE dataset_registry SET status='deleted', deleted_at=now() WHERE ckan_id = ANY(:ids)"),
            {"ids": ckan_ids},
        )
        conn.commit()
    logger.info("Marked %d datasets as deleted in registry", len(ckan_ids))


def log_pipeline_run(run: dict) -> str:
    """Insert a pipeline_runs record and return its UUID."""
    sql = text("""
        INSERT INTO pipeline_runs
            (run_type, started_at, finished_at, status,
             datasets_checked, datasets_changed, datasets_unchanged,
             rows_inserted, rows_updated, rows_soft_deleted, error_message)
        VALUES
            (:run_type, :started_at, :finished_at, :status,
             :datasets_checked, :datasets_changed, :datasets_unchanged,
             :rows_inserted, :rows_updated, :rows_soft_deleted, :error_message)
        RETURNING id
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, run).fetchone()
        conn.commit()
        return str(row[0])
