import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str


def get_settings() -> Settings:
    return Settings(
        db_path=os.getenv("OBSERVER_DB_PATH", "/data/observer.db"),
    )

