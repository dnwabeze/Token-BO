from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TrendStatus(str, Enum):
    NEW = "new"
    RISING = "rising"
    ALERTED = "alerted"
    STALE = "stale"


class SourceName(str, Enum):
    TWITTER = "Twitter/X"
    REDDIT = "Reddit"
    GOOGLE = "Google Trends"
    FOURCHAN_BIZ = "4chan /biz/"
    FOURCHAN_POL = "4chan /pol/"


@dataclass
class RawSignal:
    """One data point scraped from one source in one cycle."""

    source: SourceName
    raw_name: str           # original text as scraped (e.g. "#PepeCoin")
    url: str                # link to the source item
    raw_score: float        # source-native score (rank, upvotes, interest value, reply count)
    velocity: float         # rate of change (posts/min, upvotes/hr, etc.)
    context: str            # short description or excerpt for alert message
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TrendItem:
    """An aggregated, deduplicated trend across one or more sources."""

    slug: str                   # normalized dedup key, e.g. "pepecoin"
    canonical_name: str         # human-readable display name

    status: TrendStatus = TrendStatus.NEW

    composite_score: float = 0.0
    velocity_score: float = 0.0
    cross_source_bonus: float = 0.0
    normalized_raw_score: float = 0.0

    # Previous cycle score — used to detect velocity change between cycles
    previous_composite_score: float = 0.0

    sentiment_score: float = 0.0   # -1.0 (negative) to +1.0 (positive), from VADER

    signals: list[RawSignal] = field(default_factory=list)
    source_names: list[SourceName] = field(default_factory=list)
    source_count: int = 0

    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    last_alerted: Optional[datetime] = None
    alert_count: int = 0

    best_url: str = ""
    description: str = ""

    def add_signal(self, signal: RawSignal) -> None:
        self.signals.append(signal)
        if signal.source not in self.source_names:
            self.source_names.append(signal.source)
        self.source_count = len(self.source_names)
        self.last_seen = datetime.utcnow()
        # Keep best_url from the highest-profile source (Twitter > Reddit > Google > 4chan)
        priority = [SourceName.TWITTER, SourceName.REDDIT, SourceName.GOOGLE,
                    SourceName.FOURCHAN_BIZ, SourceName.FOURCHAN_POL]
        if not self.best_url or (
            signal.url and
            priority.index(signal.source) < priority.index(
                next((s for s in self.source_names if s != signal.source), signal.source)
            )
        ):
            self.best_url = signal.url
        if signal.context and not self.description:
            self.description = signal.context
