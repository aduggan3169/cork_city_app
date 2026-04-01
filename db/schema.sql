-- Cork Civic Tracker — Phase 1 Schema
-- SQLite init script

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ============================================================
-- LOOKUP / REFERENCE TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS parties (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    short_name  TEXT NOT NULL UNIQUE,
    colour      TEXT  -- hex colour for UI charts
);

CREATE TABLE IF NOT EXISTS wards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    seats       INTEGER NOT NULL
);

-- Self-referencing issue taxonomy (e.g. Housing → Social Housing)
CREATE TABLE IF NOT EXISTS issues (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    parent_id   INTEGER REFERENCES issues(id) ON DELETE SET NULL,
    description TEXT
);

-- ============================================================
-- CORE ENTITIES
-- ============================================================

CREATE TABLE IF NOT EXISTS councillors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    party_id    INTEGER NOT NULL REFERENCES parties(id),
    ward_id     INTEGER NOT NULL REFERENCES wards(id),
    email       TEXT,
    phone       TEXT,
    photo_url   TEXT,
    active      INTEGER NOT NULL DEFAULT 1,  -- 1 = active, 0 = resigned/removed
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meetings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    date        TEXT NOT NULL,  -- ISO 8601 date
    meeting_type TEXT NOT NULL DEFAULT 'Full Council',  -- Full Council, Committee, SPC, etc.
    minutes_url TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS motions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id  INTEGER NOT NULL REFERENCES meetings(id),
    title       TEXT NOT NULL,
    description TEXT,
    proposed_by INTEGER REFERENCES councillors(id),
    seconded_by INTEGER REFERENCES councillors(id),
    outcome     TEXT CHECK(outcome IN ('Passed', 'Failed', 'Withdrawn', 'Deferred', 'Amended')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Many-to-many: motions ↔ issues
CREATE TABLE IF NOT EXISTS motion_issues (
    motion_id   INTEGER NOT NULL REFERENCES motions(id) ON DELETE CASCADE,
    issue_id    INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    PRIMARY KEY (motion_id, issue_id)
);

-- ============================================================
-- VOTES & ATTENDANCE
-- ============================================================

CREATE TABLE IF NOT EXISTS votes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    councillor_id   INTEGER NOT NULL REFERENCES councillors(id),
    motion_id       INTEGER NOT NULL REFERENCES motions(id),
    vote            TEXT NOT NULL CHECK(vote IN ('For', 'Against', 'Abstained', 'Absent')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(councillor_id, motion_id)
);

CREATE TABLE IF NOT EXISTS attendance (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    councillor_id   INTEGER NOT NULL REFERENCES councillors(id),
    meeting_id      INTEGER NOT NULL REFERENCES meetings(id),
    present         INTEGER NOT NULL DEFAULT 1,  -- 1 = present, 0 = absent
    UNIQUE(councillor_id, meeting_id)
);

-- ============================================================
-- STATED POSITIONS (the interesting part)
-- ============================================================

-- A councillor's public stance on an issue, extracted from media/minutes.
-- Tracked independently from votes — the tension is the data.
CREATE TABLE IF NOT EXISTS positions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    councillor_id   INTEGER NOT NULL REFERENCES councillors(id),
    issue_id        INTEGER NOT NULL REFERENCES issues(id),
    stance          TEXT NOT NULL CHECK(stance IN ('Support', 'Oppose', 'Neutral', 'Mixed')),
    summary         TEXT NOT NULL,  -- brief description of stated position
    quote           TEXT,           -- direct quote if available
    date            TEXT NOT NULL,  -- when the position was stated
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- COUNCILLOR STATEMENTS PER MOTION (extracted from minutes)
-- ============================================================

-- What a councillor said during debate on a specific motion.
-- Source is typically council minutes. Multiple talking points per councillor per motion.
CREATE TABLE IF NOT EXISTS motion_statements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    councillor_id   INTEGER NOT NULL REFERENCES councillors(id),
    motion_id       INTEGER NOT NULL REFERENCES motions(id),
    summary         TEXT NOT NULL,  -- one key talking point
    quote           TEXT,           -- direct quote from minutes if available
    sentiment       TEXT CHECK(sentiment IN ('Supportive', 'Critical', 'Neutral', 'Procedural')),
    source_id       INTEGER REFERENCES sources(id),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- PROVENANCE
-- ============================================================

CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT,
    title       TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK(source_type IN ('News', 'Minutes', 'Press Release', 'Social Media', 'Interview', 'Other')),
    date        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Link positions to their sources (many-to-many)
CREATE TABLE IF NOT EXISTS position_sources (
    position_id INTEGER NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    source_id   INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    PRIMARY KEY (position_id, source_id)
);

-- Link motions to their sources
CREATE TABLE IF NOT EXISTS motion_sources (
    motion_id   INTEGER NOT NULL REFERENCES motions(id) ON DELETE CASCADE,
    source_id   INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    PRIMARY KEY (motion_id, source_id)
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_councillors_party ON councillors(party_id);
CREATE INDEX IF NOT EXISTS idx_councillors_ward ON councillors(ward_id);
CREATE INDEX IF NOT EXISTS idx_votes_councillor ON votes(councillor_id);
CREATE INDEX IF NOT EXISTS idx_votes_motion ON votes(motion_id);
CREATE INDEX IF NOT EXISTS idx_motions_meeting ON motions(meeting_id);
CREATE INDEX IF NOT EXISTS idx_positions_councillor ON positions(councillor_id);
CREATE INDEX IF NOT EXISTS idx_positions_issue ON positions(issue_id);
CREATE INDEX IF NOT EXISTS idx_attendance_councillor ON attendance(councillor_id);
CREATE INDEX IF NOT EXISTS idx_attendance_meeting ON attendance(meeting_id);
CREATE INDEX IF NOT EXISTS idx_issues_parent ON issues(parent_id);
CREATE INDEX IF NOT EXISTS idx_motion_statements_councillor ON motion_statements(councillor_id);
CREATE INDEX IF NOT EXISTS idx_motion_statements_motion ON motion_statements(motion_id);
