"""
TikTok trending hashtags scraper.
Uses TikTok Creative Center public API — no auth needed.
"""
from datetime import datetime

import httpx

from config.settings import Settings
from models.trend import RawSignal, SourceName
from scrapers.base import BaseScraper
from utils.logger import logger

# TikTok Creative Center trending hashtags API
TIKTOK_URL = (
    "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"
    "?period=7&country_code=US&page_size=20&page_num=1"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://ads.tiktok.com/",
}


class TikTokScraper(BaseScraper):
    name = "TikTok"
    source = SourceName.TWITTER  # reuse TWITTER slot — swap to new enum if desired

    def __init__(self, settings: Settings) -> None:
        pass

    async def fetch(self) -> list[RawSignal]:
        signals: list[RawSignal] = []
        try:
            async with httpx.AsyncClient(
                headers=HEADERS,
                follow_redirects=True,
                verify=False,
                timeout=15.0,
            ) as client:
                resp = await client.get(TIKTOK_URL)
                resp.raise_for_status()
                data = resp.json()

            hashtags = data.get("data", {}).get("list", [])
            for rank, item in enumerate(hashtags, start=1):
                tag = item.get("hashtag_name", "")
                if not tag:
                    continue

                publish_cnt = item.get("publish_cnt", 0) or 0
                video_views = item.get("video_views", 0) or 0

                raw_score = min(video_views / 1_000_000_000, 1.0)  # cap at 1B views
                velocity = max(0.0, 1.0 - (rank - 1) / len(hashtags))

                signals.append(RawSignal(
                    source=self.source,
                    raw_name=f"#{tag}",
                    url=f"https://www.tiktok.com/tag/{tag}",
                    raw_score=raw_score,
                    velocity=velocity,
                    context=f"#{rank} trending TikTok hashtag — {publish_cnt:,} posts, {video_views:,} views",
                    timestamp=datetime.utcnow(),
                ))

        except Exception as e:
            logger.warning(f"TikTok scraper failed ({type(e).__name__}): {e}")

        logger.info(f"TikTok: collected {len(signals)} trending hashtags")
        return signals
