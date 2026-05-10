import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str
    litellm_internal_url: str
    litellm_public_url: str
    litellm_master_key: str | None


def get_settings() -> Settings:
    return Settings(
        db_path=os.getenv("OBSERVER_DB_PATH", "/data/observer.db"),
        litellm_internal_url=os.getenv("LITELLM_INTERNAL_URL", "http://litellm-proxy:4000"),
        litellm_public_url=os.getenv("LITELLM_PUBLIC_URL", "http://localhost:4040"),
        litellm_master_key=os.getenv("LITELLM_MASTER_KEY"),
    )

