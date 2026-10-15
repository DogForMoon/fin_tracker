"""Настройки локального запуска из переменных окружения."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    token: str
    database_path: Path

    @classmethod
    def from_env(cls) -> "Config":
        token = os.environ.get("BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("Укажите BOT_TOKEN в переменных окружения.")
        return cls(token, Path(os.environ.get("DATABASE_PATH", "data/finance.sqlite3")))
