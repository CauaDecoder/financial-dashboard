from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler

from basilica_financeiro.config import Settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "created": record.created,
        }
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(settings: Settings) -> None:
    settings.paths.logs_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        settings.paths.logs_dir / "app.log",
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        handlers=[handler],
        force=True,
    )
