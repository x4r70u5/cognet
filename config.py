import os


class Config:
    """Configuration for the bot marketplace"""

    # OpenAI API configuration
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "xxxxxxxxxxxxxxxxxxxxxxxxxx")

    # Assistant ID for OpenAI Assistant API (if used)
    ASSISTANT_ID = os.environ.get("ASSISTANT_ID", "xxxxxxxxxxxxxxxxxxxxxxxxxx")

    # App settings
    DEBUG = os.environ.get("DEBUG", "True").lower() == "true"

    # Security settings (for a production deployment)
    API_KEY_HEADER = "X-API-Key"
    MARKETPLACE_SECRET = os.environ.get("MARKETPLACE_SECRET", "xxxxxxxxxxxxxxxxxxxxxxxxxx")

    # Caching settings
    CACHE_TTL = int(os.environ.get("CACHE_TTL", "3600"))  # Default: 1 hour

    # Rate limiting
    RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_PERIOD = int(os.environ.get("RATE_LIMIT_PERIOD", "60"))  # seconds