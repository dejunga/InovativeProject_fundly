from decimal import Decimal
from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import text
from database import engine

# Official fixed HRK→EUR rate (Croatia joined Eurozone 1 Jan 2023)
HRK_EUR = 7.53450

router = APIRouter(prefix="/api/financiranje", tags=["financiranje"])


def _clean(row: dict) -> dict:
    """Convert Decimal → float and HRK iznos → EUR."""
    result = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            v = float(v)
        if k in ("iznos", "ukupno", "ukupni_iznos", "ukupno_iznos") and v is not None:
            v = round(v / HRK_EUR, 2)
        result[k] = v
    return result


@router.get("")
def search_potpore(
    oib: str | None = Query(None),
    organizacija: list[str] = Query(default=[]),
    davatelj: list[str] = Query(default=[]),
    razina: list[str] = Query(default=[]),
    godina_od: int | None = Query(None),
    godina_do: int | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    filters = ["deleted_at IS NULL"]
    params: dict = {"limit": limit, "offset": offset}

    if oib:
        filters.append("oib = :oib")
        params["oib"] = oib
    if organizacija:
        filters.append("organizacija = ANY(:organizacija)")
        params["organizacija"] = organizacija
    if davatelj:
        filters.append("davatelj = ANY(:davatelj)")
        params["davatelj"] = davatelj
    if razina:
        filters.append("razina = ANY(:razina)")
        params["razina"] = razina
    if godina_od:
        filters.append("godina >= :godina_od")
        params["godina_od"] = godina_od
    if godina_do:
        filters.append("godina <= :godina_do")
        params["godina_do"] = godina_do

    where = "WHERE " + " AND ".join(filters)

    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM financijske_potpore {where}"), params).scalar()
        rows = conn.execute(text(f"""
            SELECT id, oib, organizacija, projekt, davatelj, razina,
                   zupanija_provedbe, godina, iznos
            FROM financijske_potpore
            {where}
            ORDER BY godina DESC, iznos DESC NULLS LAST
            LIMIT :limit OFFSET :offset
        """), params).mappings().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "currency": "EUR",
        "hrk_eur_rate": HRK_EUR,
        "results": [_clean(dict(r)) for r in rows],
    }


@router.get("/udruga/{oib}")
def potpore_za_udruzu(oib: str):
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT godina, razina, davatelj, projekt, iznos
            FROM financijske_potpore
            WHERE oib = :oib AND deleted_at IS NULL
            ORDER BY godina DESC, iznos DESC NULLS LAST
        """), {"oib": oib}).mappings().all()

        summary = conn.execute(text("""
            SELECT COUNT(*) AS broj_potpora, SUM(iznos) AS ukupno_iznos,
                   MIN(godina) AS prva_godina, MAX(godina) AS zadnja_godina
            FROM financijske_potpore
            WHERE oib = :oib AND deleted_at IS NULL
        """), {"oib": oib}).mappings().first()

    if not rows:
        raise HTTPException(status_code=404, detail="Nema podataka o financiranju za ovaj OIB")

    return {
        "oib": oib,
        "currency": "EUR",
        "summary": _clean(dict(summary)),
        "potpore": [_clean(dict(r)) for r in rows],
    }


@router.get("/davatelji")
def list_davatelji():
    """All distinct donors with total granted amount."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT davatelj, COUNT(*) as broj, SUM(iznos) as ukupno
            FROM financijske_potpore
            WHERE deleted_at IS NULL AND davatelj IS NOT NULL
            GROUP BY davatelj
            ORDER BY ukupno DESC NULLS LAST
        """)).mappings().all()
    return [_clean(dict(r)) for r in rows]


@router.get("/organizacije")
def search_organizacije(q: str = Query("", min_length=0)):
    """Distinct organisation names matching query (for autocomplete)."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT DISTINCT organizacija, oib, SUM(iznos) as ukupno
            FROM financijske_potpore
            WHERE deleted_at IS NULL
              AND (:q = '' OR organizacija ILIKE :q_like)
            GROUP BY organizacija, oib
            ORDER BY ukupno DESC NULLS LAST
            LIMIT 50
        """), {"q": q, "q_like": f"%{q}%"}).mappings().all()
    return [_clean(dict(r)) for r in rows]


@router.get("/statistike")
def statistike():
    with engine.connect() as conn:
        ukupno = conn.execute(text("""
            SELECT COUNT(*) as broj_potpora, SUM(iznos) as ukupni_iznos
            FROM financijske_potpore WHERE deleted_at IS NULL
        """)).mappings().first()

        po_godini = conn.execute(text("""
            SELECT godina, COUNT(*) as broj, SUM(iznos) as iznos
            FROM financijske_potpore
            WHERE deleted_at IS NULL AND godina IS NOT NULL
            GROUP BY godina ORDER BY godina DESC
        """)).mappings().all()

        top_davatelji = conn.execute(text("""
            SELECT davatelj, COUNT(*) as broj, SUM(iznos) as ukupno
            FROM financijske_potpore
            WHERE deleted_at IS NULL AND davatelj IS NOT NULL
            GROUP BY davatelj ORDER BY ukupno DESC NULLS LAST
            LIMIT 20
        """)).mappings().all()

        po_razini = conn.execute(text("""
            SELECT razina, COUNT(*) as broj, SUM(iznos) as ukupno
            FROM financijske_potpore
            WHERE deleted_at IS NULL
            GROUP BY razina ORDER BY ukupno DESC NULLS LAST
        """)).mappings().all()

    return {
        "currency": "EUR",
        "hrk_eur_rate": HRK_EUR,
        "ukupno": _clean(dict(ukupno)),
        "po_godini": [_clean(dict(r)) for r in po_godini],
        "top_davatelji": [_clean(dict(r)) for r in top_davatelji],
        "po_razini": [_clean(dict(r)) for r in po_razini],
    }
