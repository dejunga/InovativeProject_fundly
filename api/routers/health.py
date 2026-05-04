from fastapi import APIRouter
from sqlalchemy import text
from database import engine
from pipeline.ckan_client import CKANClient

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health():
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    ckan_ok = CKANClient().is_healthy()

    return {
        "status": "ok" if (db_ok and ckan_ok) else "degraded",
        "database": "ok" if db_ok else "error",
        "ckan": "ok" if ckan_ok else "error",
    }
