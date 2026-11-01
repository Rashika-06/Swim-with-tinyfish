import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
BACKEND_DIR = BASE_DIR / "backend"

# Load environment variables from .env
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    load_dotenv()

# API Keys
TINYFISH_API_KEY = os.getenv("TINYFISH_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'relief_radar.db'}")

# Application Settings
APP_NAME = "ReliefRadar"
APP_VERSION = "1.0.0"
DEFAULT_DISASTER = "South Odisha Cyclone & Flood Response (Ganjam & Gajapati)"

def is_tinyfish_configured() -> bool:
    return bool(TINYFISH_API_KEY and len(TINYFISH_API_KEY) > 5)

def is_groq_configured() -> bool:
    return bool(GROQ_API_KEY and len(GROQ_API_KEY) > 5)

def is_live_ready() -> bool:
    return is_tinyfish_configured() and is_groq_configured()
