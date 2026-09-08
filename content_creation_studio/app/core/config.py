import os
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    google_api_key: str = ""
    db_path: str = str(DATA_DIR / "studio.db")
    checkpoint_db_path: str = str(DATA_DIR / "checkpoints.db")
    gemini_model: str = "gemini-3.5-flash-lite"
    max_iterations: int = 3
    critic_threshold: int = 8

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
if settings.google_api_key:
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key
elif os.getenv("GOOGLE_API_KEY"):
    settings.google_api_key = os.getenv("GOOGLE_API_KEY", "")


def has_gemini_key() -> bool:
    return bool(settings.google_api_key and settings.google_api_key != "your_gemini_api_key_here")
