"""
evidence_store.py — SQLite-backed evidence cache.

Replaces Redis (hot) + Postgres (cold) with a single SQLite database.
SQLite ships with Python stdlib — zero extra deps, works on Render free tier.

On Render free tier the filesystem resets between deploys but persists within a
running dyno session, which is sufficient for hackathon demo purposes.

Schema mirrors the evidence_snapshots table in schema.sql exactly so the
data model is consistent between local Spring Boot and deployed Python service.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fraudguard_api.models import DeliveryStatus, EvidenceSnapshot, Tier

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DB location — use /tmp on Render (ephemeral but available within session)
# ---------------------------------------------------------------------------
_DB_PATH = Path("/tmp/fraudguard_evidence.db")
_lock = threading.Lock()


def _get_db_path() -> str:
    return str(_DB_PATH)


@contextmanager
def _conn():
    con = sqlite3.connect(_get_db_path(), check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    """Create the evidence table if it doesn't exist. Called at app startup."""
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS evidence_snapshots (
                transaction_id        INTEGER PRIMARY KEY,
                gbt_score             REAL NOT NULL,
                tier                  TEXT NOT NULL,
                transaction_amount    REAL NOT NULL,
                delivery_status       TEXT NOT NULL DEFAULT 'PENDING',
                delivery_confirmed_at TEXT,
                cached_at             TEXT NOT NULL,
                feature_snapshot_json TEXT
            )
        """)
    log.info("Evidence store initialised at %s", _get_db_path())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def cache_evidence(snapshot: EvidenceSnapshot) -> None:
    """Write (or replace) an evidence snapshot."""
    with _lock, _conn() as con:
        con.execute("""
            INSERT OR REPLACE INTO evidence_snapshots
              (transaction_id, gbt_score, tier, transaction_amount,
               delivery_status, delivery_confirmed_at, cached_at, feature_snapshot_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot.transaction_id,
            snapshot.gbt_score,
            snapshot.tier.value,
            snapshot.transaction_amount,
            snapshot.delivery_status.value,
            snapshot.delivery_confirmed_at,
            snapshot.cached_at or _now(),
            json.dumps(snapshot.feature_snapshot) if snapshot.feature_snapshot else None,
        ))
    log.debug("Cached evidence for tx %s", snapshot.transaction_id)


def get_evidence(transaction_id: int) -> Optional[EvidenceSnapshot]:
    """Retrieve a snapshot by transaction ID. Returns None if not found."""
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM evidence_snapshots WHERE transaction_id = ?",
            (transaction_id,)
        ).fetchone()

    if row is None:
        return None

    return EvidenceSnapshot(
        transaction_id=row["transaction_id"],
        gbt_score=row["gbt_score"],
        tier=Tier(row["tier"]),
        transaction_amount=row["transaction_amount"],
        delivery_status=DeliveryStatus(row["delivery_status"]),
        delivery_confirmed_at=row["delivery_confirmed_at"],
        cached_at=row["cached_at"],
        feature_snapshot=json.loads(row["feature_snapshot_json"])
        if row["feature_snapshot_json"] else None,
    )


def confirm_delivery(transaction_id: int, confirmed_at: Optional[str] = None) -> bool:
    """
    Mark delivery as CONFIRMED for a transaction.
    Returns True if the row existed and was updated, False if not found.
    """
    ts = confirmed_at or _now()
    with _lock, _conn() as con:
        cur = con.execute("""
            UPDATE evidence_snapshots
               SET delivery_status = 'CONFIRMED', delivery_confirmed_at = ?
             WHERE transaction_id = ?
        """, (ts, transaction_id))
    updated = cur.rowcount > 0
    if updated:
        log.info("Delivery confirmed for tx %s at %s", transaction_id, ts)
    else:
        log.warning("confirm_delivery: tx %s not found in evidence store", transaction_id)
    return updated


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
