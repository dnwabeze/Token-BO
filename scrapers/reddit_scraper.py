import asyncio
from datetime import datetime, timezone

import httpx

from config.settings import Settings
from models.trend import RawSignal, SourceName
from scrapers.base import BaseScraper
from utils.logger import logger

SUBREDDITS = [
    "memes",
    "dankmemes",
    "CryptoCurrency",
    "SatoshiStreetBets",
    "wallstreetbets",
    "funny",
]

HOT_LIMIT = 25
MAX_POST_AGE_HOURS = 6   # ignore posts older than this — they're not early signals

# Full browser-like headers to avoid 403
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://old.reddit.com/",
    "DNT": "1",
}


class RedditScraper(BaseScraper):
    name = "Reddit"
    source = SourceName.REDDIT

    def __init__(self, settings: Settings) -> None:
        pass

    def _parse_post(self, post: dict, subreddit: str) -> RawSignal | None:
        try:
            data = post.get("data", {})
            score = max(data.get("score", 1), 1)
            upvote_ratio = data.get("upvote_ratio", 1.0) or 1.0
            created_utc = data.get("created_utc", 0)
            permalink = data.get("permalink", "")
            title = data.get("title", "")

            if not title:
                return None

            created = datetime.fromtimestamp(created_utc, tz=timezone.utc)
            raw_age_hours = (datetime.now(tz=timezone.utc) - created).total_seconds() / 3600
            if raw_age_hours > MAX_POST_AGE_HOURS:
                return None  # too old — not an early signal

            age_hours = max(
                (datetime.now(tz=timezone.utc) - created).total_seconds() / 3600,
                0.1,
            )

            velocity = min((score * upvote_ratio) / age_hours / 5000, 1.0)
            raw_score = min(score / 50_000, 1.0)

            return RawSignal(
                source=self.source,
                raw_name=title,
                url=f"https://reddit.com{permalink}",
                raw_score=raw_score,
                velocity=velocity,
                context=f"{title} [r/{subreddit}] — {score:,} upvotes",
                timestamp=datetime.utcnow(),
            )
        except Exception as e:
            logger.warning(f"Reddit: failed to parse post: {e}")
            return None

    async def _fetch_hot(
        self,
        client: httpx.AsyncClient,
        subreddit: str,
    ) -> list[RawSignal]:
        # Use old.reddit.com — less aggressive blocking than www.reddit.com
        url = f"https://old.reddit.com/r/{subreddit}/hot.json?limit={HOT_LIMIT}&raw_json=1"
        signals: list[RawSignal] = []
        try:
            resp = await client.get(url, timeout=20.0)
            resp.raise_for_status()
            posts = resp.json().get("data", {}).get("children", [])
            for post in posts:
                sig = self._parse_post(post, subreddit)
                if sig:
                    signals.append(sig)
            await asyncio.sleep(1.5)  # respectful delay between subreddits
        except Exception as e:
            logger.warning(f"Reddit: r/{subreddit} failed: {e}")
        return signals

    async def fetch(self) -> list[RawSignal]:
        all_signals: list[RawSignal] = []
        seen: set[str] = set()

        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
            for subreddit in SUBREDDITS:
                signals = await self._fetch_hot(client, subreddit)
                for s in signals:
                    if s.raw_name not in seen:
                        seen.add(s.raw_name)
                        all_signals.append(s)

        logger.info(f"Reddit: collected {len(all_signals)} posts")
        return all_signals
