"""
Korean DCinside /bitcoin board scraper.
DCinside is South Korea's largest online community.
The bitcoin board (/biz/ equivalent) often has early meme coin discussion.
Thread titles frequently contain English coin names even if the body is Korean.
"""
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from config.settings import Settings
from models.trend import RawSignal, SourceName
from scrapers.base import BaseScraper
from utils.logger import logger

DCIN_URL = "https://gall.dcinside.com/board/lists/?id=bitcoins&list_num=50&sort_type=N"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://gall.dcinside.com/",
}

# Only flag threads whose titles contain crypto/meme-relevant English keywords
ENGLISH_KEYWORDS = re.compile(
    r"\b(coin|token|sol|solana|btc|eth|pepe|meme|pump|moon|gem|launch|"
    r"100x|1000x|airdrop|nft|defi|dex|presale|rug|based|wagmi)\b",
    re.IGNORECASE,
)

MIN_VIEWS = 50  # minimum view count to consider a thread


class KoreanScraper(BaseScraper):
    name = "DCinside KR"
    source = SourceName.FOURCHAN_POL  # reuse slot — signals treated as early/overseas

    def __init__(self, settings: Settings) -> None:
        pass

    async def fetch(self) -> list[RawSignal]:
        signals: list[RawSignal] = []
        try:
            async with httpx.AsyncClient(
                headers=HEADERS,
                follow_redirects=True,
                verify=False,
                timeout=20.0,
            ) as client:
                resp = await client.get(DCIN_URL)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")

            rows = soup.select("tr.ub-content")
            for row in rows:
                title_el = row.select_one("td.gall_tit a")
                view_el = row.select_one("td.gall_count")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                if not ENGLISH_KEYWORDS.search(title):
                    continue

                try:
                    views = int(view_el.get_text(strip=True).replace(",", "")) if view_el else 0
                except ValueError:
                    views = 0

                if views < MIN_VIEWS:
                    continue

                href = title_el.get("href", "")
                url = f"https://gall.dcinside.com{href}" if href.startswith("/") else href

                raw_score = min(views / 5000, 1.0)
                velocity = raw_score  # no previous cycle data for velocity

                signals.append(RawSignal(
                    source=self.source,
                    raw_name=title,
                    url=url,
                    raw_score=raw_score,
                    velocity=velocity,
                    context=f"Korean DCinside crypto board — {views:,} views | {title}",
                    timestamp=datetime.utcnow(),
                ))

        except Exception as e:
            logger.warning(f"Korean (DCinside) scraper failed ({type(e).__name__}): {e}")

        logger.info(f"DCinside KR: collected {len(signals)} threads")
        return signals
