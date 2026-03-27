import asyncio
import warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

from alerts.telegram_bot import TelegramAlerter
from config.settings import settings
from core.aggregator import Aggregator
from core.scheduler import build_scheduler, run_scrape_cycle
from db.database import init_db
from scrapers.fourchan_scraper import FourchanScraper
from scrapers.korean_scraper import KoreanScraper
from scrapers.reddit_scraper import RedditScraper
from scrapers.tiktok_scraper import TikTokScraper
from scrapers.twitter_scraper import TwitterScraper
from utils.logger import logger


async def main() -> None:
    logger.info("Trend Bot starting up…")

    conn = init_db(settings.database_path)
    logger.info(f"Database ready at {settings.database_path}")

    scrapers = [
        TwitterScraper(settings),
        TikTokScraper(settings),
        RedditScraper(settings),
        FourchanScraper(settings),
        KoreanScraper(settings),
    ]

    aggregator = Aggregator(conn)
    alerter = TelegramAlerter(settings, conn)

    await run_scrape_cycle(scrapers, aggregator, alerter, settings)

    scheduler = build_scheduler(scrapers, aggregator, alerter, settings)
    scheduler.start()
    logger.info(
        f"Scheduler running — next cycle in {settings.scrape_interval_minutes} minutes"
    )
    logger.info(f"Daily summary scheduled at {settings.daily_summary_hour:02d}:00 UTC")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown(wait=False)
        conn.close()
        logger.info("Trend Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
