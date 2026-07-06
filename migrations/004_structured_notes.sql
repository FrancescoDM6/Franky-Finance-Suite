-- Migration 004: Structured note analyses
-- Persists parsed note terms + Monte Carlo valuations so analyses
-- survive page reloads. Distinct from the user-text `notes` table.

CREATE SEQUENCE IF NOT EXISTS structured_notes_id_seq;
CREATE TABLE IF NOT EXISTS structured_notes (
    id INTEGER PRIMARY KEY DEFAULT nextval('structured_notes_id_seq'),
    label TEXT NOT NULL,
    isin TEXT,
    issuer TEXT,
    tickers JSON,
    status TEXT DEFAULT 'analyzed',
    note_json JSON NOT NULL,
    valuation_json JSON,
    alternatives_json JSON,
    narrative TEXT,
    source_filename TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_structured_notes_created ON structured_notes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_structured_notes_issuer ON structured_notes(issuer);
