import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

class Settings(BaseModel):
    PROJECT_NAME: str = "Autopsy"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api"
    HOST: str = "127.0.0.1"
    PORT: int = 8008

    # Model configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

    # Live Search Configuration
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")
    GOOGLE_SEARCH_API_KEY: str = os.getenv("GOOGLE_SEARCH_API_KEY", "")
    GOOGLE_SEARCH_CX: str = os.getenv("GOOGLE_SEARCH_CX", "")

    # Dual Co-Operating Models (Model 1: Gemini Extraction, Model 2: OpenRouter Reasoning)
    EXTRACTOR_MODEL: str = os.getenv("EXTRACTOR_MODEL", "gemini-3.6-flash")
    REASONER_MODEL: str = os.getenv("REASONER_MODEL", "openai/gpt-4o-mini")

    # Scoring Weights for the policy drift report
    W1_EVIDENCE_DIVERSITY: float = 25.0
    W2_SEVERITY_WEIGHT: float = 30.0
    W3_SKEPTIC_RESISTANCE: float = 35.0
    W4_TIMEZONE_SKEW_UNCERTAINTY: float = 15.0

    # Thresholds
    STANDARD_SURFACE_THRESHOLD: float = 80.0
    DEGRADED_SURFACE_THRESHOLD: float = 90.0
    PASSIVE_LOG_THRESHOLD: float = 50.0

    # Storage
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    USE_SQLITE_FTS_FALLBACK: bool = True

settings = Settings()
