from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str
    telegram_chat_id: str

    # Twitter / X (cookie-based auth)
    twitter_auth_token: str = ""
    twitter_ct0: str = ""
    twitter_twid: str = ""
    twitter_kdt: str = ""
    twitter_woeid: int = 1

    # Google Trends
    google_trends_geo: str = "US"
    google_trends_language: str = "en-US"

    # Scoring
    alert_threshold: float = 0.30
    re_alert_cooldown_hours: int = 2
    score_increase_threshold: float = 0.10

    # Scheduling
    scrape_interval_minutes: int = 10

    # Storage
    database_path: Path = Path("data/trends.db")

    # 4chan
    fourchan_min_replies: int = 20

    # Alert controls
    max_alerts_per_hour: int = 5
    daily_summary_hour: int = 8      # UTC hour for daily summary (0-23)

    # Feature flags
    competitor_check_enabled: bool = True
    charts_enabled: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def reload(self) -> None:
        """Re-read .env and update all fields in place."""
        fresh = Settings()
        for field_name in self.model_fields:
            setattr(self, field_name, getattr(fresh, field_name))


settings = Settings()
