-- Migration 001: Initial Schema
-- Creates all base tables for Phinan Suite

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User context storage for persistent assistant memory
CREATE TABLE IF NOT EXISTS user_context (
    id INTEGER PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    value_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_user_context_key ON user_context(key);

-- Chat history for assistant conversations
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chat_history_session ON chat_history(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_created ON chat_history(created_at DESC);

-- User notes with semantic search support
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    note_type TEXT DEFAULT 'general',
    tags TEXT[],
    ticker_symbols TEXT[],
    metadata JSON,
    embedding FLOAT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_notes_type ON notes(note_type);
CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at DESC);

-- Research data for ticker analysis
CREATE TABLE IF NOT EXISTS research (
    id INTEGER PRIMARY KEY,
    ticker_symbol TEXT NOT NULL,
    research_type TEXT NOT NULL,
    data JSON NOT NULL,
    sentiment_score FLOAT,
    volatility_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_research_ticker ON research(ticker_symbol);
CREATE INDEX IF NOT EXISTS idx_research_type ON research(research_type);
CREATE INDEX IF NOT EXISTS idx_research_created ON research(created_at DESC);

-- Portfolio holdings
CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY,
    ticker_symbol TEXT NOT NULL,
    quantity DECIMAL(18, 8) NOT NULL,
    cost_basis DECIMAL(18, 4) NOT NULL,
    purchase_date DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_portfolio_ticker ON portfolio(ticker_symbol);

-- Options positions
CREATE TABLE IF NOT EXISTS options_positions (
    id INTEGER PRIMARY KEY,
    ticker_symbol TEXT NOT NULL,
    option_type TEXT NOT NULL,
    strike_price DECIMAL(18, 4) NOT NULL,
    expiration_date DATE NOT NULL,
    quantity INTEGER NOT NULL,
    premium DECIMAL(18, 4) NOT NULL,
    position_type TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_options_ticker ON options_positions(ticker_symbol);
CREATE INDEX IF NOT EXISTS idx_options_expiration ON options_positions(expiration_date);
CREATE INDEX IF NOT EXISTS idx_options_status ON options_positions(status);

-- Market data cache
CREATE TABLE IF NOT EXISTS market_data_cache (
    id INTEGER PRIMARY KEY,
    ticker_symbol TEXT NOT NULL,
    data_type TEXT NOT NULL,
    data JSON NOT NULL,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    UNIQUE(ticker_symbol, data_type)
);
CREATE INDEX IF NOT EXISTS idx_market_cache_ticker ON market_data_cache(ticker_symbol);
CREATE INDEX IF NOT EXISTS idx_market_cache_expires ON market_data_cache(expires_at);
