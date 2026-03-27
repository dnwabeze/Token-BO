import sqlite3
from pathlib import Path


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trends (
            slug                TEXT PRIMARY KEY,
            canonical_name      TEXT NOT NULL,
            status              TEXT DEFAULT 'new',
            composite_score     REAL DEFAULT 0.0,
            previous_score      REAL DEFAULT 0.0,
            velocity_score      REAL DEFAULT 0.0,
            cross_source_bonus  REAL DEFAULT 0.0,
            normalized_raw      REAL DEFAULT 0.0,
            source_count        INTEGER DEFAULT 0,
            source_names        TEXT DEFAULT '',
            first_seen          TEXT NOT NULL,
            last_seen           TEXT NOT NULL,
            last_alerted        TEXT,
            alert_count         INTEGER DEFAULT 0,
            best_url            TEXT DEFAULT '',
            description         TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS signals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            slug        TEXT NOT NULL,
            source      TEXT NOT NULL,
            raw_name    TEXT NOT NULL,
            url         TEXT DEFAULT '',
            raw_score   REAL DEFAULT 0.0,
            velocity    REAL DEFAULT 0.0,
            context     TEXT DEFAULT '',
            timestamp   TEXT NOT NULL,
            FOREIGN KEY (slug) REFERENCES trends(slug)
        );

        CREATE TABLE IF NOT EXISTS alert_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            slug            TEXT NOT NULL,
            composite_score REAL,
            source_count    INTEGER,
            sent_at         TEXT NOT NULL,
            message_text    TEXT
        );

        CREATE TABLE IF NOT EXISTS score_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            slug            TEXT NOT NULL,
            composite_score REAL NOT NULL,
            recorded_at     TEXT NOT NULL
        );


        CREATE INDEX IF NOT EXISTS idx_score_history_slug ON score_history(slug);
        CREATE INDEX IF NOT EXISTS idx_signals_slug ON signals(slug);
        CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp);
        CREATE INDEX IF NOT EXISTS idx_trends_status ON trends(status);
        CREATE INDEX IF NOT EXISTS idx_trends_score ON trends(composite_score DESC);
    """)
    conn.commit()
    # Add new columns to existing DBs without failing
    _add_column_if_missing(conn, "trends", "sentiment_score", "REAL DEFAULT 0.0")
    return conn


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.commit()
