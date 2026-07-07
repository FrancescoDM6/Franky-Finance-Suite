"""Persistence for logged options trades.

Pure functions taking the database manager (notes/portfolio style) so
tests can pass a mock. Rows returned to the state layer are JSON-safe
(dates stringified).
"""

import logging
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

# Columns the edit dialog may change
EDITABLE_COLUMNS = {
    "strike_price",
    "premium",
    "quantity",
    "strategy",
    "expiration_date",
    "notes",
    "opened_at",
}


def add_trade(db, trade: dict) -> int:
    """Insert a new open trade and return its id."""
    row = db.query("SELECT nextval('options_positions_id_seq') AS id")
    trade_id = int(row[0]["id"])

    db.execute(
        """
        INSERT INTO options_positions (
            id, ticker_symbol, option_type, strike_price, expiration_date,
            quantity, premium, position_type, strategy, status, opened_at, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
        """,
        (
            trade_id,
            trade["ticker_symbol"],
            trade["option_type"],
            trade["strike_price"],
            trade["expiration_date"],
            trade["quantity"],
            trade["premium"],
            trade["position_type"],
            trade["strategy"],
            trade["opened_at"],
            trade.get("notes", ""),
        ),
    )
    return trade_id


def _stringify(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat(sep=" ", timespec="seconds") if isinstance(
            value, datetime
        ) else value.isoformat()
    return str(value)


def list_trades(db, status: Optional[str] = None, limit: int = 200) -> List[dict]:
    """List trades, optionally filtered to open or closed-or-expired."""
    where = ""
    params: tuple = ()
    if status == "open":
        where = "WHERE status = 'open'"
    elif status == "closed_or_expired":
        where = "WHERE status IN ('closed', 'expired')"

    rows = db.query(
        f"""
        SELECT id, ticker_symbol, option_type, strike_price, expiration_date,
               quantity, premium, position_type, strategy, status,
               exit_price, realized_pnl, opened_at, closed_at, notes
        FROM options_positions
        {where}
        ORDER BY opened_at DESC
        LIMIT ?
        """,
        params + (limit,),
    )

    result = []
    for row in rows:
        result.append(
            {
                "id": int(row["id"]),
                "ticker_symbol": row.get("ticker_symbol") or "",
                "option_type": row.get("option_type") or "",
                "strike_price": float(row.get("strike_price") or 0),
                "expiration_date": _stringify(row.get("expiration_date")),
                "quantity": int(row.get("quantity") or 0),
                "premium": float(row.get("premium") or 0),
                "position_type": row.get("position_type") or "",
                "strategy": row.get("strategy") or "",
                "status": row.get("status") or "open",
                "exit_price": (
                    float(row["exit_price"]) if row.get("exit_price") is not None else None
                ),
                "realized_pnl": (
                    float(row["realized_pnl"])
                    if row.get("realized_pnl") is not None
                    else None
                ),
                "opened_at": _stringify(row.get("opened_at")),
                "closed_at": _stringify(row.get("closed_at")),
                "notes": row.get("notes") or "",
            }
        )
    return result


def close_trade(
    db,
    trade_id: int,
    exit_price: float,
    realized_pnl: float,
    status: str,
    closed_at: Optional[str] = None,
) -> None:
    """Close or expire an open trade with its realized P/L."""
    if status not in ("closed", "expired"):
        raise ValueError(f"Invalid close status: {status}")
    closed_at = closed_at or datetime.now().isoformat(sep=" ", timespec="seconds")
    db.execute(
        """
        UPDATE options_positions
        SET status = ?, exit_price = ?, realized_pnl = ?, closed_at = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, exit_price, realized_pnl, closed_at, trade_id),
    )


def update_trade(db, trade_id: int, fields: dict) -> None:
    """Update editable columns of a trade (whitelisted)."""
    updates = {k: v for k, v in fields.items() if k in EDITABLE_COLUMNS}
    if not updates:
        return
    set_clause = ", ".join(f"{column} = ?" for column in updates)
    db.execute(
        f"""
        UPDATE options_positions
        SET {set_clause}, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        tuple(updates.values()) + (trade_id,),
    )


def delete_trade(db, trade_id: int) -> None:
    """Delete a logged trade."""
    db.execute("DELETE FROM options_positions WHERE id = ?", (trade_id,))


def count_closed_trades(db) -> int:
    """Number of closed/expired trades (gates the LLM pattern card)."""
    rows = db.query(
        "SELECT COUNT(*) AS n FROM options_positions WHERE status IN ('closed', 'expired')"
    )
    return int(rows[0]["n"]) if rows else 0
