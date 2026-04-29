from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    whisper_assets_dir: Path = Path(__file__).parents[1] / "assets"
    whisper_models_dir: Path = Path.home() / ".whisper"
    whisper_use_cuda: bool | None = None
    whisper_model: str = "large-v3"
    azure_speech_api_key: str | None = None
    azure_service_region: str | None = None
    worker_slot_id: str | None = None
    worker_role: str = "whisper"
