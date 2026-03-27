"""
CoinGecko Trending scraper.
Shows the top trending coins/tokens by search volume on CoinGecko.
Free, no API key needed, directly relevant for meme coin discovery.
"""
from datetime import datetime

import httpx

from config.settings import Settings
from models.trend import RawSignal, SourceName
from scrapers.base import BaseScraper
from utils.logger import logger

TRENDING_URL = "https://api.coingecko.com/api/v3/search/trending"

HEADERS = {
    "User-Agent": "TrendBot/1.0",
    "Accept": "application/json",
}


class GoogleTrendsScraper(BaseScraper):
    """CoinGecko Trending — replaces Google Trends."""
    name = "CoinGecko Trending"
    source = SourceName.GOOGLE  # reuses GOOGLE slot in the scoring system

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
                resp = await client.get(TRENDING_URL)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning(f"CoinGecko Trending: fetch failed ({type(e).__name__}): {e}")
            return signals

        coins = data.get("coins", [])
        nfts = data.get("nfts", [])

        # Process trending coins
        for rank, entry in enumerate(coins, start=1):
            item = entry.get("item", {})
            name = item.get("name", "")
            symbol = item.get("symbol", "")
            score = item.get("score", 0)  # 0 = most trending
            market_cap_rank = item.get("market_cap_rank") or 9999
            thumb = item.get("thumb", "")
            coin_id = item.get("id", "")

            if not name:
                continue

            # Higher raw_score for lower market cap rank (smaller = more established)
            # But we want early/new coins so boost lower market_cap_rank coins less
            raw_score = max(0.0, 1.0 - rank / (len(coins) + 1))

            url = f"https://www.coingecko.com/en/coins/{coin_id}"
            context = (
                f"#{rank} trending on CoinGecko — ${symbol.upper()}"
                + (f", market cap rank #{market_cap_rank}" if market_cap_rank < 9999 else ", unranked (new)")
            )

            signals.append(RawSignal(
                source=self.source,
                raw_name=f"{name} ${symbol.upper()}",
                url=url,
                raw_score=raw_score,
                velocity=raw_score,
                context=context,
                timestamp=datetime.utcnow(),
            ))

        # Process trending NFTs
        for rank, nft in enumerate(nfts, start=1):
            name = nft.get("name", "")
            symbol = nft.get("symbol", "")
            nft_id = nft.get("id", "")
            if not name:
                continue

            raw_score = max(0.0, 0.5 - rank / (len(nfts) * 2 + 1))
            url = f"https://www.coingecko.com/en/nft/{nft_id}"

            signals.append(RawSignal(
                source=self.source,
                raw_name=f"{name} NFT",
                url=url,
                raw_score=raw_score,
                velocity=raw_score,
                context=f"#{rank} trending NFT on CoinGecko — {symbol}",
                timestamp=datetime.utcnow(),
            ))

        logger.info(f"CoinGecko Trending: collected {len(signals)} trending coins/NFTs")
        return signals
