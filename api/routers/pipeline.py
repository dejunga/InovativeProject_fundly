import threading
from fastapi import APIRouter, Query
from sqlalchemy import text
from database import engine

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

_run_lock = threading.Lock()
_running = False


@router.get("/runs")
def list_runs(limit: int = Query(20, ge=1, le=100)):
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, run_type, started_at, finished_at, status,
                   datasets_checked, datasets_changed, datasets_unchanged,
                   rows_inserted, rows_updated, rows_soft_deleted, error_message
            FROM pipeline_runs
            ORDER BY started_at DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM pipeline_runs WHERE id = :id"),
            {"id": run_id},
        ).mappings().first()

    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Run not found")

    return dict(row)


@router.post("/run")
def trigger_run():
    """Trigger a manual pipeline run in the background."""
    global _running

    if not _lock_and_set():
        return {"status": "already_running", "message": "A pipeline run is already in progress."}

    def _run():
        global _running
        try:
            from pipeline.orchestrator import run
            run(run_type="manual")
        finally:
            _running = False

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"status": "started", "message": "Pipeline run started in background."}


@router.get("/status")
def pipeline_status():
    return {"running": _running}


def _lock_and_set() -> bool:
    global _running
    with _run_lock:
        if _running:
            return False
        _running = True
        return True
