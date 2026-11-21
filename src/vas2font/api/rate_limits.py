from vas2font.api.config import get_settings
from vas2font.api.security import RateLimiter

settings = get_settings()
open_project_limiter = RateLimiter(settings.open_rate_limit)
font_generation_limiter = RateLimiter(settings.generation_rate_limit)
