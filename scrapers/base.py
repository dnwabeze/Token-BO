from abc import ABC, abstractmethod

from models.trend import RawSignal, SourceName


class BaseScraper(ABC):
    name: str
    source: SourceName

    @abstractmethod
    async def fetch(self) -> list[RawSignal]:
        """
        Fetch raw signals from the source.
        Must be async. Must NOT raise — catch and log all exceptions internally.
        Returns an empty list on failure.
        """
        ...

    def normalize_score(self, raw: float, max_val: float = 100.0) -> float:
        """Normalize a raw score to 0.0–1.0."""
        if max_val <= 0:
            return 0.0
        return min(raw / max_val, 1.0)
