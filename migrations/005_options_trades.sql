-- Migration 005: Options trade logging fields
-- Adds strategy labels and realized P/L accounting to options_positions.

ALTER TABLE options_positions ADD COLUMN IF NOT EXISTS strategy TEXT;
ALTER TABLE options_positions ADD COLUMN IF NOT EXISTS exit_price DECIMAL(18, 4);
ALTER TABLE options_positions ADD COLUMN IF NOT EXISTS realized_pnl DECIMAL(18, 4);

-- Backfill strategy for any pre-existing rows from type/position.
UPDATE options_positions SET strategy = CASE
    WHEN position_type = 'long'  AND option_type = 'call' THEN 'long_call'
    WHEN position_type = 'long'  AND option_type = 'put'  THEN 'long_put'
    WHEN position_type = 'short' AND option_type = 'call' THEN 'covered_call'
    WHEN position_type = 'short' AND option_type = 'put'  THEN 'cash_secured_put'
END
WHERE strategy IS NULL;

CREATE INDEX IF NOT EXISTS idx_options_strategy ON options_positions(strategy);
