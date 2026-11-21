import base64
import hashlib
import secrets
import time
from collections import defaultdict

from fastapi import Request

from vas2font.api.errors import ApiError


def generate_access_code() -> str:
    encoded = base64.b32encode(secrets.token_bytes(16)).decode("ascii").rstrip("=")
    return "-".join(encoded[index : index + 5] for index in range(0, len(encoded), 5))


def normalize_access_code(value: str) -> str:
    normalized = value.replace("-", "").replace(" ", "").upper()
    if len(normalized) != 26:
        raise ApiError(401, "invalid_access_code", "The project access code is invalid")
    try:
        base64.b32decode(normalized + "=" * 6)
    except ValueError as error:
        raise ApiError(
            401, "invalid_access_code", "The project access code is invalid"
        ) from error
    return normalized


def access_code_hash(value: str) -> str:
    return hashlib.sha256(normalize_access_code(value).encode("ascii")).hexdigest()


def bearer_code(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise ApiError(401, "invalid_access_code", "The project access code is invalid")
    return authorization.removeprefix("Bearer ").strip()


class RateLimiter:
    def __init__(self, limit: int, period_seconds: int = 60) -> None:
        self.limit = limit
        self.period_seconds = period_seconds
        self.events: dict[str, list[float]] = defaultdict(list)

    def check(self, request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        events = [
            event for event in self.events[key] if now - event < self.period_seconds
        ]
        if len(events) >= self.limit:
            raise ApiError(
                429, "rate_limit_exceeded", "Too many requests; try again later"
            )
        events.append(now)
        self.events[key] = events
