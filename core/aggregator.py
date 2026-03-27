import sqlite3
from datetime import datetime

from core.scorer import compute_score
from core.sentiment import get_sentiment
from db import queries
from models.trend import RawSignal, TrendItem, TrendStatus
from utils.logger import logger
from utils.text_utils import make_slug, find_matching_slug


class Aggregator:
    """Merges raw signals from all scrapers into deduplicated TrendItems."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def process(self, all_signals: list[RawSignal]) -> list[TrendItem]:
        """
        Given a flat list of RawSignals from the current cycle:
        1. Group by slug (with fuzzy matching for near-duplicates)
        2. Load existing DB state for those slugs
        3. Score each TrendItem
        4. Persist to DB
        Returns all TrendItems sorted by composite_score descending.
        """
        # Collect existing slugs from DB for fuzzy dedup
        existing_slugs = queries.get_recent_slugs(self._conn, hours=48)

        # Map: canonical_slug → TrendItem
        items: dict[str, TrendItem] = {}

        for signal in all_signals:
            new_slug = make_slug(signal.raw_name)
            if not new_slug:
                continue

            # Fuzzy match against existing DB slugs AND already-seen slugs this cycle
            all_known = list(set(existing_slugs) | set(items.keys()))
            matched = find_matching_slug(new_slug, all_known)
            slug = matched if matched else new_slug

            if slug not in items:
                # Load from DB if it exists
                db_row = queries.get_trend(self._conn, slug)
                if db_row:
                    trend = _row_to_trend(db_row)
                else:
                    trend = TrendItem(
                        slug=slug,
                        canonical_name=signal.raw_name,
                        first_seen=datetime.utcnow(),
                        last_seen=datetime.utcnow(),
                    )
                items[slug] = trend

            items[slug].add_signal(signal)

        # Fetch previous signal scores for velocity calculation
        scored: list[TrendItem] = []
        for slug, trend in items.items():
            prev_scores: dict[str, float] = {}
            for source in trend.source_names:
                prev = queries.get_previous_signal_score(self._conn, slug, source)
                if prev is not None:
                    prev_scores[source.value] = prev

            trend.previous_composite_score = trend.composite_score
            compute_score(trend, previous_signals=prev_scores)

            # Update status
            if trend.composite_score > trend.previous_composite_score + 0.05:
                trend.status = TrendStatus.RISING
            elif trend.status not in (TrendStatus.ALERTED, TrendStatus.STALE):
                trend.status = TrendStatus.NEW

            # Sentiment: average over all signal contexts
            all_text = " ".join(s.context for s in trend.signals if s.context)
            trend.sentiment_score = get_sentiment(all_text)

            # Persist trend + signals + score history
            queries.upsert_trend(self._conn, trend)
            queries.insert_score_history(self._conn, slug, trend.composite_score)
            for signal in trend.signals:
                queries.insert_signal(self._conn, slug, signal)

            scored.append(trend)
            logger.debug(
                f"Trend [{slug}] score={trend.composite_score:.3f} "
                f"sources={trend.source_count} status={trend.status.value}"
            )

        scored.sort(key=lambda t: t.composite_score, reverse=True)
        logger.info(f"Aggregator: processed {len(scored)} unique trends from {len(all_signals)} signals")
        return scored


def _row_to_trend(row: dict) -> TrendItem:
    from models.trend import SourceName, TrendStatus

    source_names = []
    for name in (row.get("source_names") or "").split(","):
        name = name.strip()
        if name:
            try:
                source_names.append(SourceName(name))
            except ValueError:
                pass

    def parse_dt(val):
        if val is None:
            return None
        try:
            return datetime.fromisoformat(val)
        except Exception:
            return datetime.utcnow()

    return TrendItem(
        slug=row["slug"],
        canonical_name=row["canonical_name"],
        status=TrendStatus(row.get("status", "new")),
        composite_score=row.get("composite_score", 0.0),
        previous_composite_score=row.get("previous_score", 0.0),
        velocity_score=row.get("velocity_score", 0.0),
        cross_source_bonus=row.get("cross_source_bonus", 0.0),
        normalized_raw_score=row.get("normalized_raw", 0.0),
        source_count=row.get("source_count", 0),
        source_names=source_names,
        first_seen=parse_dt(row.get("first_seen")) or datetime.utcnow(),
        last_seen=parse_dt(row.get("last_seen")) or datetime.utcnow(),
        last_alerted=parse_dt(row.get("last_alerted")),
        alert_count=row.get("alert_count", 0),
        best_url=row.get("best_url", ""),
        description=row.get("description", ""),
    )
