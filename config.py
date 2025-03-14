import os


class Config:
    """Configuration for the bot marketplace"""

    # OpenAI API configuration
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "sk-proj-th7O0TDxNuaquYBpSDNmT3BlbkFJEmzfeNiVV2odwL2cRe3n")

    # Assistant ID for OpenAI Assistant API (if used)
    ASSISTANT_ID = os.environ.get("ASSISTANT_ID", "asst_u8RnZ84waVaMqXDQcfNVKI7M")

    # App settings
    DEBUG = os.environ.get("DEBUG", "True").lower() == "true"

    # Security settings (for a production deployment)
    API_KEY_HEADER = "X-API-Key"
    MARKETPLACE_SECRET = os.environ.get("MARKETPLACE_SECRET", "vj1DvJhVQECFLY2_cltrPxAI6p4hlzJW5Be98LBgTo0=")

    # Caching settings
    CACHE_TTL = int(os.environ.get("CACHE_TTL", "3600"))  # Default: 1 hour

    # Rate limiting
    RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_PERIOD = int(os.environ.get("RATE_LIMIT_PERIOD", "60"))  # seconds