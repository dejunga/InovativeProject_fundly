from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import text
from database import engine

router = APIRouter(prefix="/api/udruge", tags=["udruge"])


@router.get("")
def search_udruge(
    naziv: str | None = Query(None, description="Search by name (case-insensitive, partial match)"),
    zupanija: str | None = Query(None, description="Filter by county"),
    status: str | None = Query(None, description="active | deleted (default: active only)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    filters = ["deleted_at IS NULL"] if not status else []

    if status == "deleted":
        filters = ["deleted_at IS NOT NULL"]
    elif status == "all":
        filters = []

    params: dict = {"limit": limit, "offset": offset}

    if naziv:
        filters.append("naziv ILIKE :naziv")
        params["naziv"] = f"%{naziv}%"

    if zupanija:
        filters.append("zupanija ILIKE :zupanija")
        params["zupanija"] = f"%{zupanija}%"

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    count_sql = f"SELECT COUNT(*) FROM udruge {where}"
    data_sql = f"""
        SELECT id, naziv, skraceni_naziv, oib, zupanija, adresa,
               datum_osnivanja, datum_brisanja, djelatnosti, updated_at
        FROM udruge
        {where}
        ORDER BY naziv ASC NULLS LAST
        LIMIT :limit OFFSET :offset
    """

    with engine.connect() as conn:
        total = conn.execute(text(count_sql), params).scalar()
        rows = conn.execute(text(data_sql), params).mappings().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": [dict(r) for r in rows],
    }


@router.get("/zupanije")
def list_zupanije():
    """Return all distinct county names with counts."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT zupanija, COUNT(*) as count
            FROM udruge
            WHERE deleted_at IS NULL AND zupanija IS NOT NULL
            GROUP BY zupanija
            ORDER BY zupanija
        """)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/{udruga_id}")
def get_udruga(udruga_id: str):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM udruge WHERE id = :id"),
            {"id": udruga_id},
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Udruga not found")

    return dict(row)
