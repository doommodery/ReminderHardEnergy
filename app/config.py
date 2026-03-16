from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    telegram_bot_token: str = Field(alias='TELEGRAM_BOT_TOKEN')
    telegram_chat_ids: str = Field(alias='TELEGRAM_CHAT_IDS')
    source_url: str = Field(alias='SOURCE_URL')
    source_sheet_name: str = Field(default='График судов', alias='SOURCE_SHEET_NAME')
    sync_hour: int = Field(default=3, alias='SYNC_HOUR')
    default_event_time: str = Field(default='09:00', alias='DEFAULT_EVENT_TIME')
    tz: str = Field(default='Europe/Moscow', alias='TZ')
    db_path: str = Field(default='data/bot.db', alias='DB_PATH')
    file_cache_path: str = Field(default='data/source.xlsx', alias='FILE_CACHE_PATH')
    log_level: str = Field(default='INFO', alias='LOG_LEVEL')

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    @property
    def chat_id_list(self) -> list[int]:
        result: list[int] = []
        for part in self.telegram_chat_ids.split(','):
            part = part.strip()
            if not part:
                continue
            result.append(int(part))
        if not result:
            raise ValueError('TELEGRAM_CHAT_IDS is empty')
        return result


settings = Settings()
