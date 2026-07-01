"""Application settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR.parent / "data"


class Settings(BaseSettings):
    """Runtime configuration."""

    model_config = SettingsConfigDict(env_prefix="WIND_TRACK_")

    api_port: int = 8002
    frontend_port: int = 5181
    db_path: Path = DATA_DIR / "wind_track.db"
    cors_origins: list[str] = [
        "http://localhost:5181",
        "http://127.0.0.1:5181",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    default_area_slug: str = "pilot_presquile"
    scalar_model_slug: str = "scalar-v0.1"
    pipeline_version: str = "0.5.0"
    precompute_directions: list[int] = [0, 45, 90, 135, 180, 225, 270, 315]


settings = Settings()