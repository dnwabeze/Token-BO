import re
from datetime import datetime, timezone

import httpx

from config.settings import Settings
from models.trend import RawSignal, SourceName
from scrapers.base import BaseScraper
from utils.logger import logger
from utils.text_utils import strip_html, truncate

# Boards to monitor
BOARDS = [
    ("biz", SourceName.FOURCHAN_BIZ),
    ("pol", SourceName.FOURCHAN_POL),
]

# Keywords that indicate meme/coin potential
MEME_KEYWORDS = re.compile(
    r"\b(coin|token|launch|moon|gem|100x|1000x|meme|pepe|wojak|chad|based|"
    r"pump|fud|shill|airdrop|presale|dex|defi|nft|sol|solana|eth|btc|"
    r"crypto|early|bullish|bearish|rug|wagmi|ngmi|gm|ser|anon)\b",
    re.IGNORECASE,
)


class FourchanScraper(BaseScraper):
    name = "4chan"
    source = SourceName.FOURCHAN_BIZ  # overridden per board

    def __init__(self, settings: Settings) -> None:
        self._min_replies = settings.fourchan_min_replies

    async def _fetch_board(
        self,
        client: httpx.AsyncClient,
        board: str,
        source: SourceName,
    ) -> list[RawSignal]:
        url = f"https://a.4cdn.org/{board}/catalog.json"
        signals: list[RawSignal] = []

        try:
            resp = await client.get(url, timeout=15.0)
            resp.raise_for_status()
            pages = resp.json()
        except Exception as e:
            logger.warning(f"4chan /{board}/: fetch failed: {e}")
            return signals

        for page in pages:
            for thread in page.get("threads", []):
                replies = thread.get("replies", 0)
                if replies < self._min_replies:
                    continue

                subject = thread.get("sub", "") or ""
                comment = strip_html(thread.get("com", "") or "")
                text_body = f"{subject} {comment}"

                # Filter: must contain at least one meme/coin keyword
                if not MEME_KEYWORDS.search(text_body):
                    continue

                thread_no = thread["no"]
                thread_url = f"https://boards.4channel.org/{board}/thread/{thread_no}"

                # Age in hours
                now_ts = datetime.now(tz=timezone.utc).timestamp()
                last_modified = thread.get("last_modified", now_ts)
                age_hours = max((now_ts - last_modified) / 3600, 0.1)

                # velocity: replies per hour (cap at 200/hr = 1.0)
                velocity = min(replies / age_hours / 200, 1.0)

                # raw_score: reply count, cap at 500 = 1.0
                raw_score = min(replies / 500, 1.0)

                display_name = subject if subject else truncate(comment, 80)
                context_text = truncate(f"{subject} — {comment}" if subject else comment, 200)

                signals.append(RawSignal(
                    source=source,
                    raw_name=display_name,
                    url=thread_url,
                    raw_score=raw_score,
                    velocity=velocity,
                    context=f"4chan /{board}/ — {replies} replies | {context_text}",
                    timestamp=datetime.utcnow(),
                ))

        return signals

    async def fetch(self) -> list[RawSignal]:
        all_signals: list[RawSignal] = []
        async with httpx.AsyncClient(
            headers={"User-Agent": "TrendBot/1.0"},
            follow_redirects=True,
            verify=False,
        ) as client:
            for board, source in BOARDS:
                signals = await self._fetch_board(client, board, source)
                all_signals.extend(signals)
                logger.info(f"4chan /{board}/: collected {len(signals)} threads")

        return all_signals
