import asyncio
import sqlite3

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from alerts.telegram_bot import TelegramAlerter
from core.aggregator import Aggregator
from config.settings import Settings
from models.trend import RawSignal
from scrapers.base import BaseScraper
from utils.logger import logger


async def run_scrape_cycle(
    scrapers: list[BaseScraper],
    aggregator: Aggregator,
    alerter: TelegramAlerter,
    settings: Settings,
) -> None:
    # Hot reload .env settings at the start of each cycle
    try:
        settings.reload()
    except Exception:
        pass

    logger.info("=== Scrape cycle starting ===")

    results = await asyncio.gather(
        *[scraper.fetch() for scraper in scrapers],
        return_exceptions=True,
    )

    all_signals: list[RawSignal] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Scraper '{scrapers[i].name}' raised: {result}")
        else:
            all_signals.extend(result)

    logger.info(f"Total raw signals this cycle: {len(all_signals)}")

    if not all_signals:
        logger.warning("No signals collected — skipping aggregation")
        return

    trends = aggregator.process(all_signals)
    alert_count = await alerter.process_trends(trends)

    logger.info(f"=== Cycle complete — {len(trends)} trends, {alert_count} alerts sent ===")


def build_scheduler(
    scrapers: list[BaseScraper],
    aggregator: Aggregator,
    alerter: TelegramAlerter,
    settings: Settings,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    # Main scrape cycle
    scheduler.add_job(
        run_scrape_cycle,
        trigger=IntervalTrigger(minutes=settings.scrape_interval_minutes),
        args=[scrapers, aggregator, alerter, settings],
        id="scrape_cycle",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    # Daily summary — fires every day at the configured UTC hour
    scheduler.add_job(
        alerter.send_daily_summary,
        trigger=CronTrigger(hour=settings.daily_summary_hour, minute=0, timezone="UTC"),
        id="daily_summary",
        replace_existing=True,
        max_instances=1,
    )

    return scheduler
