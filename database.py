import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://antonio:password@localhost:5432/hr_open_data")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS dataset_registry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ckan_id         TEXT UNIQUE NOT NULL,
    ckan_name       TEXT NOT NULL,
    title           TEXT,
    organization    TEXT,
    file_hash       TEXT,
    last_modified   TIMESTAMPTZ,
    last_synced_at  TIMESTAMPTZ,
    refresh_freq    TEXT,
    row_count       INTEGER,
    status          TEXT DEFAULT 'active',
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_type            TEXT,
    started_at          TIMESTAMPTZ NOT NULL,
    finished_at         TIMESTAMPTZ,
    status              TEXT,
    datasets_checked    INTEGER DEFAULT 0,
    datasets_changed    INTEGER DEFAULT 0,
    datasets_unchanged  INTEGER DEFAULT 0,
    rows_inserted       INTEGER DEFAULT 0,
    rows_updated        INTEGER DEFAULT 0,
    rows_soft_deleted   INTEGER DEFAULT 0,
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS udruge (
    id                  TEXT PRIMARY KEY,
    naziv               TEXT,
    skraceni_naziv      TEXT,
    oib                 TEXT,
    zupanija            TEXT,
    adresa              TEXT,
    datum_osnivanja     DATE,
    datum_brisanja      DATE,
    djelatnosti         JSONB,
    row_hash            TEXT,
    source_dataset_id   TEXT REFERENCES dataset_registry(ckan_id),
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ,
    deleted_at          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_udruge_zupanija ON udruge(zupanija);
CREATE INDEX IF NOT EXISTS idx_udruge_datum_osnivanja ON udruge(datum_osnivanja);
CREATE INDEX IF NOT EXISTS idx_udruge_deleted ON udruge(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_udruge_oib ON udruge(oib) WHERE oib IS NOT NULL;

CREATE TABLE IF NOT EXISTS financijske_potpore (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    oib                 TEXT,               -- links to udruge.oib
    organizacija        TEXT NOT NULL,      -- name as it appears in source
    projekt             TEXT,
    davatelj            TEXT,               -- who gave the money
    razina              TEXT,               -- 'drzava' | 'zupanija' | 'grad' | 'opcina'
    zupanija_provedbe   TEXT,
    godina              INTEGER NOT NULL,
    iznos               NUMERIC(15, 2),
    row_hash            TEXT,
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ,
    deleted_at          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_potpore_oib    ON financijske_potpore(oib) WHERE oib IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_potpore_godina ON financijske_potpore(godina);
CREATE INDEX IF NOT EXISTS idx_potpore_davatelj ON financijske_potpore(davatelj);
"""


def migrate():
    with engine.connect() as conn:
        conn.execute(text(SCHEMA_SQL))
        conn.commit()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
