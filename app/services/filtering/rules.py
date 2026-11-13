from app.core.config import get_settings


_settings = get_settings()

MIN_FOLLOWERS = _settings.min_followers
MAX_FOLLOWERS = _settings.max_followers
TARGET_PLATFORM = "youtube"
TARGET_NICHE = _settings.target_niche.strip().lower()

FITNESS_KEYWORDS = [
    "fitness",
    "workout",
    "gym",
    "bodybuilding",
    "strength training",
    "weight training",
    "muscle building",
    "home workout",
    "fitness coach",
    "personal trainer",
    "nutrition",
    "weight loss",
    "weightlifting",
    "powerlifting",
    "calisthenics",
    "exercise",
    "fat loss",
    "yoga",
    "sports nutrition",
]