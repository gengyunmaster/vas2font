import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    frontend_dist: Path
    max_upload_bytes: int
    generation_concurrency: int
    generation_timeout_seconds: float
    open_rate_limit: int
    generation_rate_limit: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://vas2font:vas2font@localhost:55432/vas2font",
        ),
        frontend_dist=Path(
            os.getenv("FRONTEND_DIST", str(Path("frontend/dist").resolve()))
        ),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(128 * 1024 * 1024))),
        generation_concurrency=int(os.getenv("GENERATION_CONCURRENCY", "1")),
        generation_timeout_seconds=float(
            os.getenv("GENERATION_TIMEOUT_SECONDS", "120")
        ),
        open_rate_limit=int(os.getenv("OPEN_RATE_LIMIT", "10")),
        generation_rate_limit=int(os.getenv("GENERATION_RATE_LIMIT", "20")),
    )
