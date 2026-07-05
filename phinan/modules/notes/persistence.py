"""Persistence for structured note analyses.

Pure functions taking the database manager (portfolio SQL style), so
tests can pass a mock. All payloads are stored as JSON strings and
rehydrated through the Pydantic models.
"""

import json
import logging
from typing import List, Optional

from ...models.structured_note import (
    AlternativeResult,
    NoteAnalysis,
    SimulationResult,
    StructuredNote,
)

logger = logging.getLogger(__name__)


def _label_for(analysis: NoteAnalysis) -> str:
    note = analysis.note
    parts = [p for p in [note.issuer, note.product_name] if p]
    if not parts:
        parts = [", ".join(note.underlying_tickers) or "Untitled note"]
    return " - ".join(parts)


def save_analysis(db, analysis: NoteAnalysis, source_filename: str = "") -> int:
    """Insert an analysis and return its id."""
    row = db.query("SELECT nextval('structured_notes_id_seq') AS id")
    analysis_id = int(row[0]["id"])

    db.execute(
        """
        INSERT INTO structured_notes (
            id, label, isin, issuer, tickers, status,
            note_json, valuation_json, alternatives_json,
            narrative, source_filename
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            analysis_id,
            _label_for(analysis),
            analysis.note.isin,
            analysis.note.issuer,
            json.dumps(analysis.note.underlying_tickers),
            "analyzed",
            analysis.note.model_dump_json(),
            analysis.simulation.model_dump_json(),
            json.dumps([a.model_dump(mode="json") for a in analysis.alternatives]),
            analysis.narrative,
            source_filename,
        ),
    )
    return analysis_id


def update_narrative(db, analysis_id: int, narrative: str) -> None:
    """Attach/refresh the narrative on an existing analysis."""
    db.execute(
        """
        UPDATE structured_notes
        SET narrative = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (narrative, analysis_id),
    )


def list_analyses(db, limit: int = 50) -> List[dict]:
    """Recent analyses with headline numbers (single query, no N+1)."""
    rows = db.query(
        """
        SELECT
            id,
            label,
            issuer,
            source_filename,
            created_at,
            TRY_CAST(valuation_json->>'$.fair_value_pct' AS DOUBLE) AS fair_value_pct,
            TRY_CAST(valuation_json->>'$.implied_fee_pct' AS DOUBLE) AS implied_fee_pct
        FROM structured_notes
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    result = []
    for row in rows:
        created = row.get("created_at")
        result.append(
            {
                "id": int(row["id"]),
                "label": row.get("label") or "Untitled note",
                "issuer": row.get("issuer") or "",
                "source_filename": row.get("source_filename") or "",
                "created_at": (
                    created.strftime("%Y-%m-%d %H:%M")
                    if hasattr(created, "strftime")
                    else str(created or "")
                ),
                "fair_value_pct": row.get("fair_value_pct"),
                "implied_fee_pct": row.get("implied_fee_pct"),
            }
        )
    return result


def _model_from_json(model_cls, payload):
    """Rehydrate a model from a JSON column (string or already-parsed)."""
    if payload is None:
        return None
    if isinstance(payload, str):
        return model_cls.model_validate_json(payload)
    return model_cls.model_validate(payload)


def load_analysis(db, analysis_id: int) -> Optional[NoteAnalysis]:
    """Load one full analysis bundle by id."""
    rows = db.query(
        """
        SELECT note_json, valuation_json, alternatives_json, narrative
        FROM structured_notes WHERE id = ?
        """,
        (analysis_id,),
    )
    if not rows:
        return None
    row = rows[0]
    try:
        note = _model_from_json(StructuredNote, row["note_json"])
        simulation = _model_from_json(SimulationResult, row["valuation_json"])
        alternatives_raw = row.get("alternatives_json")
        if isinstance(alternatives_raw, str):
            alternatives_raw = json.loads(alternatives_raw)
        alternatives = [
            AlternativeResult.model_validate(a) for a in (alternatives_raw or [])
        ]
        return NoteAnalysis(
            note=note,
            simulation=simulation,
            alternatives=alternatives,
            narrative=row.get("narrative") or "",
        )
    except Exception as e:
        logger.error("Could not load structured note analysis %s: %s", analysis_id, e)
        return None


def delete_analysis(db, analysis_id: int) -> None:
    """Delete a saved analysis."""
    db.execute("DELETE FROM structured_notes WHERE id = ?", (analysis_id,))
