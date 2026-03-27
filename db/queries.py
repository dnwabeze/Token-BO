import sqlite3
from datetime import datetime
from typing import Optional

from models.trend import RawSignal, TrendItem, TrendStatus, SourceName


# ── Trends ────────────────────────────────────────────────────────────────────

def upsert_trend(conn: sqlite3.Connection, trend: TrendItem) -> None:
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO trends (
            slug, canonical_name, status, composite_score, previous_score,
            velocity_score, cross_source_bonus, normalized_raw,
            source_count, source_names, first_seen, last_seen,
            last_alerted, alert_count, best_url, description, sentiment_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            canonical_name     = excluded.canonical_name,
            status             = excluded.status,
            previous_score     = composite_score,
            composite_score    = excluded.composite_score,
            velocity_score     = excluded.velocity_score,
            cross_source_bonus = excluded.cross_source_bonus,
            normalized_raw     = excluded.normalized_raw,
            source_count       = excluded.source_count,
            source_names       = excluded.source_names,
            last_seen          = excluded.last_seen,
            last_alerted       = excluded.last_alerted,
            alert_count        = excluded.alert_count,
            best_url           = excluded.best_url,
            description        = excluded.description,
            sentiment_score    = excluded.sentiment_score
    """, (
        trend.slug,
        trend.canonical_name,
        trend.status.value,
        trend.composite_score,
        trend.previous_composite_score,
        trend.velocity_score,
        trend.cross_source_bonus,
        trend.normalized_raw_score,
        trend.source_count,
        ",".join(s.value for s in trend.source_names),
        trend.first_seen.isoformat(),
        trend.last_seen.isoformat(),
        trend.last_alerted.isoformat() if trend.last_alerted else None,
        trend.alert_count,
        trend.best_url,
        trend.description,
        trend.sentiment_score,
    ))
    conn.commit()


def get_trend(conn: sqlite3.Connection, slug: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM trends WHERE slug = ?", (slug,)
    ).fetchone()
    return dict(row) if row else None


def get_all_trends(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM trends ORDER BY composite_score DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_recent_slugs(conn: sqlite3.Connection, hours: int = 24) -> list[str]:
    """Return slugs seen within the last N hours (for dedup matching)."""
    cutoff = datetime.utcnow().replace(
        hour=datetime.utcnow().hour - hours if datetime.utcnow().hour >= hours else 0,
        minute=0, second=0, microsecond=0
    ).isoformat()
    rows = conn.execute(
        "SELECT slug FROM trends WHERE last_seen >= ?", (cutoff,)
    ).fetchall()
    return [r["slug"] for r in rows]


def mark_alerted(conn: sqlite3.Connection, slug: str, message: str, score: float, source_count: int) -> None:
    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE trends SET status = 'alerted', last_alerted = ?, alert_count = alert_count + 1 WHERE slug = ?",
        (now, slug)
    )
    conn.execute(
        "INSERT INTO alert_log (slug, composite_score, source_count, sent_at, message_text) VALUES (?, ?, ?, ?, ?)",
        (slug, score, source_count, now, message)
    )
    conn.commit()


# ── Signals ───────────────────────────────────────────────────────────────────

def insert_signal(conn: sqlite3.Connection, slug: str, signal: RawSignal) -> None:
    conn.execute("""
        INSERT INTO signals (slug, source, raw_name, url, raw_score, velocity, context, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        slug,
        signal.source.value,
        signal.raw_name,
        signal.url,
        signal.raw_score,
        signal.velocity,
        signal.context,
        signal.timestamp.isoformat(),
    ))
    conn.commit()


def get_previous_signal_score(conn: sqlite3.Connection, slug: str, source: SourceName) -> Optional[float]:
    """Get the most recent raw_score for this slug+source from the previous cycle."""
    row = conn.execute("""
        SELECT raw_score FROM signals
        WHERE slug = ? AND source = ?
        ORDER BY timestamp DESC
        LIMIT 1 OFFSET 1
    """, (slug, source.value)).fetchone()
    return row["raw_score"] if row else None


# ── Score History ──────────────────────────────────────────────────────────────

def insert_score_history(conn: sqlite3.Connection, slug: str, score: float) -> None:
    conn.execute(
        "INSERT INTO score_history (slug, composite_score, recorded_at) VALUES (?, ?, ?)",
        (slug, score, datetime.utcnow().isoformat()),
    )
    conn.commit()


def get_score_history(conn: sqlite3.Connection, slug: str, limit: int = 12) -> list[tuple[str, float]]:
    """Return last N (timestamp, score) pairs for a trend, oldest first."""
    rows = conn.execute("""
        SELECT recorded_at, composite_score FROM score_history
        WHERE slug = ?
        ORDER BY recorded_at DESC
        LIMIT ?
    """, (slug, limit)).fetchall()
    return [(r["recorded_at"], r["composite_score"]) for r in reversed(rows)]


# ── Alert dedup ────────────────────────────────────────────────────────────────

def get_recent_alerted_slugs(conn: sqlite3.Connection, limit: int = 20) -> list[str]:
    """Return slugs of the most recently alerted trends (for dedup check)."""
    rows = conn.execute("""
        SELECT slug FROM alert_log
        ORDER BY sent_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return [r["slug"] for r in rows]


def get_alerts_sent_since(conn: sqlite3.Connection, since_iso: str) -> int:
    """Count how many alerts were sent since a given ISO timestamp (for rate limiting)."""
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM alert_log WHERE sent_at >= ?", (since_iso,)
    ).fetchone()
    return row["cnt"] if row else 0


# ── Daily Summary ──────────────────────────────────────────────────────────────

def get_top_trends_last_24h(conn: sqlite3.Connection, limit: int = 5) -> list[dict]:
    """Return the top N trends by peak composite_score in the last 24 hours."""
    rows = conn.execute("""
        SELECT t.slug, t.canonical_name, t.composite_score, t.source_count,
               t.source_names, t.best_url, t.alert_count
        FROM trends t
        WHERE t.last_seen >= datetime('now', '-24 hours')
        ORDER BY t.composite_score DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]
