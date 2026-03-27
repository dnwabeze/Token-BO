import asyncio
from datetime import datetime
from urllib.parse import quote_plus

from twikit import Client

from config.settings import Settings
from models.trend import RawSignal, SourceName
from scrapers.base import BaseScraper
from utils.logger import logger

TOP_N_TRENDS = 30


class TwitterScraper(BaseScraper):
    name = "Twitter/X"
    source = SourceName.TWITTER

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Client | None = None

    async def _get_client(self) -> Client | None:
        if self._client is not None:
            return self._client

        s = self._settings
        if not s.twitter_auth_token:
            logger.warning("Twitter: no cookies configured — skipping (set TWITTER_AUTH_TOKEN in .env)")
            return None

        client = Client(language="en-US")
        # Set cookies directly — no password login needed
        client.set_cookies({
            "auth_token": s.twitter_auth_token,
            "ct0":        s.twitter_ct0,
            "twid":       s.twitter_twid,
            "kdt":        s.twitter_kdt,
        })
        self._client = client
        logger.info("Twitter: loaded cookies from .env")
        return client

    async def fetch(self) -> list[RawSignal]:
        try:
            client = await self._get_client()
            if client is None:
                return []
            trends = await client.get_trends("trending")
        except Exception as e:
            logger.error(f"Twitter scraper failed: {e}")
            self._client = None
            return []

        signals: list[RawSignal] = []
        for rank, trend in enumerate(trends[:TOP_N_TRENDS], start=1):
            try:
                name = trend.name if hasattr(trend, "name") else str(trend)
                tweet_volume = getattr(trend, "tweet_count", 0) or 0
                raw_score = max(0.0, 1.0 - (rank - 1) / TOP_N_TRENDS)
                velocity = min(tweet_volume / 1_000_000, 1.0)
                url = f"https://twitter.com/search?q={quote_plus(name)}&f=live"

                signals.append(RawSignal(
                    source=self.source,
                    raw_name=name,
                    url=url,
                    raw_score=raw_score,
                    velocity=velocity,
                    context=f"Trending on Twitter/X — rank #{rank}" +
                            (f", ~{tweet_volume:,} tweets" if tweet_volume else ""),
                    timestamp=datetime.utcnow(),
                ))
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.warning(f"Twitter: failed to parse trend at rank {rank}: {e}")

        logger.info(f"Twitter: collected {len(signals)} trending topics")
        return signals
