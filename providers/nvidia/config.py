from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class NVIDIASettings(BaseSettings):
    # Do not provide a fake credential. Load the real project .env regardless of cwd.
    api_key: str = ""
    model: str = "nvidia/nemotron-3-super-120b-a12b"
    base_url: str = "https://integrate.api.nvidia.com/v1"

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_prefix="NVIDIA_",
        extra="ignore",
    )


settings = NVIDIASettings()
