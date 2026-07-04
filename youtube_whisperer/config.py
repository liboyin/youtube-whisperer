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
    redis_host: str = "redis"
    redis_port: int = 6379
    worker_slot_id: str | None = None
    worker_role: str = "whisper"
    # Idle threshold before a worker claims a PEL entry owned by another (likely dead) consumer.
    # Set conservatively above the longest plausible transcription so an in-flight task on a live
    # worker is never stolen; only genuinely stranded tasks are recovered. Defaults to 6 hours.
    worker_claim_min_idle_seconds: int = 21600
