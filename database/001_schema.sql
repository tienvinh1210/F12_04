-- Livestock Dashboard — Supabase/PostgreSQL Schema
-- Run this in Supabase SQL Editor (Phase 0)

-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- FARMS
-- ============================================================
CREATE TABLE farms (
    farm_id     TEXT PRIMARY KEY,
    farm_name   TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO farms (farm_id, farm_name, slug) VALUES
    ('KF', 'Killara Feedlot', 'killara-feedlot');

-- ============================================================
-- USERS (custom auth — not Supabase Auth required)
-- ============================================================
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,          -- scrypt hash (compatible with R shinymanager format)
    is_admin        BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Default users — CHANGE PASSWORDS IN PRODUCTION
-- Password hashes below are placeholders; generate real scrypt hashes on seed:
-- Python: from passlib.hash import scrypt; scrypt.hash("admin123")
-- Or use bcrypt and re-hash on first login migration
INSERT INTO users (username, password_hash, is_admin) VALUES
    ('admin', '$scrypt$placeholder_admin123', TRUE),
    ('owner', '$scrypt$placeholder_owner123', TRUE),
    ('user',  '$scrypt$placeholder_user123',  FALSE);

-- ============================================================
-- USER ↔ FARM ACCESS
-- ============================================================
CREATE TABLE user_farm_access (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    farm_id     TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, farm_id)
);

-- Grant all seeded users access to KF
INSERT INTO user_farm_access (user_id, farm_id)
SELECT id, 'KF' FROM users;

-- ============================================================
-- ANIMAL DATA (main fact table)
-- ============================================================
CREATE TABLE animal_data (
    id                  BIGSERIAL PRIMARY KEY,
    farm_id             TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
    eid                 TEXT NOT NULL,
    date                DATE NOT NULL,
    breed               TEXT,
    treatment           TEXT,
    mob                 TEXT,
    sex                 TEXT,
    weight              DOUBLE PRECISION,
    pweight             DOUBLE PRECISION,
    growthpbs           DOUBLE PRECISION,
    finalpweight        DOUBLE PRECISION,
    finalgrowthpbs      DOUBLE PRECISION,
    finaldailygrowth    DOUBLE PRECISION,
    feedintakekgd       DOUBLE PRECISION,
    feedintakepct       DOUBLE PRECISION,
    methane             DOUBLE PRECISION,
    animalvalue         DOUBLE PRECISION,
    animalprod          DOUBLE PRECISION,
    feedintakekgdsum     DOUBLE PRECISION,
    finalgrowthpbssum   DOUBLE PRECISION,
    animalprodsum       DOUBLE PRECISION,
    methanesum          DOUBLE PRECISION,
    methanesupplsum     DOUBLE PRECISION,
    carcassweight       DOUBLE PRECISION,
    dressedcarcass      DOUBLE PRECISION,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (farm_id, eid, date)
);

CREATE INDEX idx_animal_farm_date ON animal_data (farm_id, date);
CREATE INDEX idx_animal_farm_eid ON animal_data (farm_id, eid);
CREATE INDEX idx_animal_farm_breed ON animal_data (farm_id, breed);
CREATE INDEX idx_animal_farm_treatment ON animal_data (farm_id, treatment);
CREATE INDEX idx_animal_farm_mob ON animal_data (farm_id, mob);
CREATE INDEX idx_animal_farm_sex ON animal_data (farm_id, sex);
CREATE INDEX idx_animal_farm_year ON animal_data (farm_id, (EXTRACT(YEAR FROM date)));

-- ============================================================
-- DATA SNAPSHOTS (replaces DuckDB backups)
-- ============================================================
CREATE TABLE animal_data_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    farm_id         TEXT NOT NULL REFERENCES farms(farm_id),
    snapshot_name   TEXT NOT NULL,
    record_count    INTEGER NOT NULL,
    storage_path    TEXT,                   -- optional: JSON/CSV in Supabase Storage
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT
);

-- ============================================================
-- EMAIL SCHEDULES
-- ============================================================
CREATE TABLE email_schedules (
    id              SERIAL PRIMARY KEY,
    farm_id         TEXT NOT NULL REFERENCES farms(farm_id),
    recipient_email VARCHAR(255) NOT NULL,
    schedule_name   VARCHAR(255),
    frequency       VARCHAR(50) NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly', 'once')),
    send_time       TIME NOT NULL DEFAULT '09:00:00',
    send_date       DATE,                   -- for 'once'
    day_of_week     INTEGER CHECK (day_of_week BETWEEN 1 AND 7),  -- 1=Monday
    day_of_month    INTEGER CHECK (day_of_month BETWEEN 1 AND 31),
    next_send_at    TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_sent       TIMESTAMPTZ,
    email_subject   VARCHAR(500) DEFAULT 'Automated Livestock Report',
    email_body      TEXT DEFAULT '',
    report_filters  JSONB,
    report_charts   TEXT[] DEFAULT ARRAY['Distribution', 'Summary Statistics'],
    report_format   TEXT DEFAULT 'PDF' CHECK (report_format IN ('PDF', 'HTML', 'PRINT_HTML')),
    created_by      VARCHAR(100)
);

CREATE INDEX idx_email_schedules_active ON email_schedules (is_active, next_send_at);
CREATE INDEX idx_email_schedules_farm ON email_schedules (farm_id);

-- ============================================================
-- UPLOAD LOG
-- ============================================================
CREATE TABLE data_uploads (
    id              BIGSERIAL PRIMARY KEY,
    farm_id         TEXT NOT NULL REFERENCES farms(farm_id),
    filename        TEXT NOT NULL,
    rows_inserted   INTEGER DEFAULT 0,
    rows_skipped    INTEGER DEFAULT 0,
    rows_overwritten INTEGER DEFAULT 0,
    duplicate_mode  TEXT CHECK (duplicate_mode IN ('skip', 'overwrite')),
    storage_path    TEXT,
    uploaded_by     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- ROW LEVEL SECURITY (enable after seeding)
-- ============================================================
ALTER TABLE animal_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE farms ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS; app uses service role on backend only.
-- If using Supabase client from browser, add policies per user_farm_access.

-- Example policy (custom JWT with farm_id claim):
-- CREATE POLICY animal_data_farm_isolation ON animal_data
--   FOR SELECT USING (farm_id = current_setting('app.farm_id', true));

-- ============================================================
-- HELPER: updated_at trigger
-- ============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER farms_updated_at BEFORE UPDATE ON farms
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- STORAGE BUCKETS (create in Supabase Dashboard or API)
-- ============================================================
-- Bucket: logos          → path: {farm_id}/01_university.png
-- Bucket: uploads        → path: {farm_id}/archive/{filename}
-- Bucket: reports        → path: {farm_id}/generated/{uuid}.pdf
