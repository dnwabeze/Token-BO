import asyncio
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import quote

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config.settings import Settings
from core.competitor_checker import find_solana_competitors, format_competitors
from core.sentiment import sentiment_label
from core.token_suggester import suggest_tickers
from db import queries
from models.trend import TrendItem, TrendStatus
from utils.chart import generate_score_chart
from utils.logger import logger
from utils.text_utils import escape_markdown_v2, truncate

TOTAL_SOURCES = 4


# ── Alert eligibility ─────────────────────────────────────────────────────────

def _should_alert(trend: TrendItem, settings: Settings, conn: sqlite3.Connection) -> bool:
    if trend.composite_score < settings.alert_threshold:
        return False

    # Cooldown check
    if trend.last_alerted is not None:
        cooldown = timedelta(hours=settings.re_alert_cooldown_hours)
        if datetime.utcnow() - trend.last_alerted < cooldown:
            return False
        if trend.composite_score - trend.previous_composite_score < settings.score_increase_threshold:
            return False

    # Rate limiting: max N alerts per hour
    one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    alerts_this_hour = queries.get_alerts_sent_since(conn, one_hour_ago)
    if alerts_this_hour >= settings.max_alerts_per_hour:
        logger.info(f"Rate limit reached ({alerts_this_hour}/{settings.max_alerts_per_hour}/hr) — suppressing alert for [{trend.slug}]")
        return False

    # Duplicate dedup: suppress if a very similar slug was just alerted
    recent_slugs = queries.get_recent_alerted_slugs(conn, limit=20)
    from utils.text_utils import jaccard_similarity
    for recent in recent_slugs:
        if recent != trend.slug and jaccard_similarity(trend.slug, recent) > 0.70:
            logger.info(f"Dedup suppressed [{trend.slug}] — similar to recently alerted [{recent}]")
            return False

    return True


# ── Message formatting ────────────────────────────────────────────────────────

def _format_alert(trend: TrendItem, competitors: list[dict]) -> str:
    esc = escape_markdown_v2

    status_emoji = {
        TrendStatus.NEW:     "🆕",
        TrendStatus.RISING:  "📈",
        TrendStatus.ALERTED: "🔔",
        TrendStatus.STALE:   "📉",
    }.get(trend.status, "•")

    # Sources
    source_lines = "\n".join(f"  • {esc(src.value)}" for src in trend.source_names)

    # Description
    description = truncate(trend.description, 220)

    # Scoring explainer
    score_breakdown = (
        f"  └ Popularity: `{trend.normalized_raw_score:.2f}`\n"
        f"  └ Velocity:   `{trend.velocity_score:.2f}`\n"
        f"  └ Cross\\-src: `{trend.cross_source_bonus:.2f}`"
    )

    # Sentiment
    sentiment = sentiment_label(trend.sentiment_score)

    # Age
    age_minutes = int((datetime.utcnow() - trend.first_seen).total_seconds() / 60)
    age_str = f"{age_minutes}m ago" if age_minutes < 60 else f"{age_minutes // 60}h {age_minutes % 60}m ago"

    # Token suggestions
    tickers = suggest_tickers(trend.canonical_name)
    ticker_str = "  " + "  ".join(esc(t) for t in tickers) if tickers else "  N/A"

    # Competitors
    comp_str = esc(format_competitors(competitors))

    alert_num = trend.alert_count + 1

    lines = [
        f"*{esc('🔥 TREND DETECTED')}*",
        "",
        f"*Name:* {esc(trend.canonical_name)}",
        f"*Score:* `{trend.composite_score:.2f}` \\| *Sources:* `{trend.source_count}/{TOTAL_SOURCES}` \\| {status_emoji} {esc(trend.status.value.upper())}",
        f"*Sentiment:* {sentiment}",
        "",
        "*Score Breakdown:*",
        score_breakdown,
        "",
        "*Active on:*",
        esc(source_lines),
        "",
        "*Context:*",
        f"_{esc(description)}_" if description else "_No context_",
        "",
        "*🎯 Token Name Ideas:*",
        ticker_str,
        "",
        "*⚔️ Existing Solana Tokens:*",
        comp_str,
        "",
    ]

    if trend.best_url:
        lines.append(f"*Link:* {esc(trend.best_url)}")
        lines.append("")

    lines.append(f"_First seen: {esc(age_str)} \\| Alert \\#{alert_num}_")
    return "\n".join(lines)


def _build_keyboard(trend: TrendItem) -> InlineKeyboardMarkup:
    keyword = quote(trend.canonical_name)
    buttons = [
        [
            InlineKeyboardButton(
                "🐦 Search Twitter",
                url=f"https://twitter.com/search?q={keyword}&f=live",
            ),
            InlineKeyboardButton(
                "📊 Dexscreener",
                url=f"https://dexscreener.com/search?q={keyword}",
            ),
        ],
        [
            InlineKeyboardButton(
                "🚀 pump.fun",
                url="https://pump.fun",
            ),
            InlineKeyboardButton(
                "📰 Source",
                url=trend.best_url or "https://reddit.com",
            ),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


# ── Daily summary ─────────────────────────────────────────────────────────────

def _format_daily_summary(top_trends: list[dict]) -> str:
    esc = escape_markdown_v2
    lines = [f"*{esc('📊 DAILY TREND SUMMARY')}*", ""]
    if not top_trends:
        lines.append("_No significant trends in the last 24 hours\\._")
    else:
        for i, t in enumerate(top_trends, start=1):
            name = esc(t["canonical_name"])
            score = t["composite_score"]
            sources = t["source_count"]
            alerted = t["alert_count"]
            lines.append(
                f"{i}\\. *{name}* — score `{score:.2f}` \\| {sources} sources \\| {alerted} alerts"
            )
    lines += ["", "_Top 5 trends from the last 24h_"]
    return "\n".join(lines)


# ── Alerter class ─────────────────────────────────────────────────────────────

class TelegramAlerter:
    def __init__(self, settings: Settings, conn: sqlite3.Connection) -> None:
        self._bot = Bot(token=settings.telegram_bot_token)
        self._chat_id = settings.telegram_chat_id
        self._settings = settings
        self._conn = conn

    async def process_trends(self, trends: list[TrendItem]) -> int:
        sent = 0
        for trend in trends:
            if not _should_alert(trend, self._settings, self._conn):
                continue
            try:
                # Competitor check
                competitors: list[dict] = []
                if self._settings.competitor_check_enabled:
                    competitors = await find_solana_competitors(trend.canonical_name)

                message = _format_alert(trend, competitors)
                keyboard = _build_keyboard(trend)

                # Try to send chart if enabled and history exists
                sent_ok = False
                if self._settings.charts_enabled:
                    history = queries.get_score_history(self._conn, trend.slug, limit=10)
                    chart_buf = generate_score_chart(trend.slug, history)
                    if chart_buf:
                        try:
                            short_caption = (
                                f"🔥 *{escape_markdown_v2(trend.canonical_name)}* — "
                                f"Score: `{trend.composite_score:.2f}` \\| "
                                f"Sources: `{trend.source_count}/{TOTAL_SOURCES}`\n"
                                f"Sentiment: {sentiment_label(trend.sentiment_score)}"
                            )
                            await self._bot.send_photo(
                                chat_id=self._chat_id,
                                photo=chart_buf,
                                caption=short_caption,
                                parse_mode=ParseMode.MARKDOWN_V2,
                                reply_markup=keyboard,
                            )
                            # Send full details as follow-up text
                            await self._bot.send_message(
                                chat_id=self._chat_id,
                                text=message,
                                parse_mode=ParseMode.MARKDOWN_V2,
                                disable_web_page_preview=True,
                            )
                            sent_ok = True
                        except Exception:
                            pass  # Fall through to plain message

                if not sent_ok:
                    await self._bot.send_message(
                        chat_id=self._chat_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN_V2,
                        disable_web_page_preview=False,
                        reply_markup=keyboard,
                    )

                queries.mark_alerted(
                    self._conn,
                    trend.slug,
                    message,
                    trend.composite_score,
                    trend.source_count,
                )
                trend.last_alerted = datetime.utcnow()
                trend.alert_count += 1
                sent += 1
                logger.info(f"Alert sent for [{trend.slug}] score={trend.composite_score:.2f} sentiment={trend.sentiment_score:.2f}")
                await asyncio.sleep(0.5)

            except TelegramError as e:
                logger.error(f"Telegram send failed for [{trend.slug}]: {e}")
            except Exception as e:
                logger.error(f"Unexpected alert error for [{trend.slug}]: {e}")

        return sent

    async def send_daily_summary(self) -> None:
        try:
            top = queries.get_top_trends_last_24h(self._conn, limit=5)
            message = _format_daily_summary(top)
            await self._bot.send_message(
                chat_id=self._chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=True,
            )
            logger.info("Daily summary sent")
        except Exception as e:
            logger.error(f"Daily summary failed: {e}")
