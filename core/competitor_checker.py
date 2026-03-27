"""
Checks Dexscreener for existing Solana tokens matching a trend keyword.
If a token already exists with high volume, the opportunity may be gone.
"""
from urllib.parse import quote

import httpx

from utils.logger import logger

DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/search"


async def find_solana_competitors(keyword: str) -> list[dict]:
    """
    Search Dexscreener for existing Solana tokens matching the keyword.
    Returns up to 3 results sorted by 24h volume descending.
    Each result dict has: name, symbol, price_usd, volume_24h, url
    """
    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            resp = await client.get(DEXSCREENER_URL, params={"q": keyword})
            resp.raise_for_status()
            pairs = resp.json().get("pairs") or []

        solana_pairs = [p for p in pairs if p.get("chainId") == "solana"]
        solana_pairs.sort(
            key=lambda p: float((p.get("volume") or {}).get("h24") or 0),
            reverse=True,
        )

        results = []
        for pair in solana_pairs[:3]:
            base = pair.get("baseToken", {})
            vol = float((pair.get("volume") or {}).get("h24") or 0)
            price = pair.get("priceUsd") or "?"
            results.append({
                "name":       base.get("name", "?"),
                "symbol":     base.get("symbol", "?"),
                "price_usd":  price,
                "volume_24h": vol,
                "url":        pair.get("url", ""),
            })
        return results

    except Exception as e:
        logger.debug(f"Competitor check failed for '{keyword}': {e}")
        return []


def format_competitors(competitors: list[dict]) -> str:
    """Format competitor list for Telegram message."""
    if not competitors:
        return "None found — opportunity may be open!"
    lines = []
    for c in competitors:
        vol = c["volume_24h"]
        vol_str = f"${vol:,.0f}" if vol >= 1 else "<$1"
        lines.append(f"  • {c['name']} (${c['symbol']}) — 24h vol {vol_str}")
    return "\n".join(lines)
