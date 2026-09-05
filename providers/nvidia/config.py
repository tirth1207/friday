from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class NVIDIASettings(BaseSettings):
    api_key: str = "mock_key_for_dev"
    model: str = "nvidia/nemotron-4-340b-instruct"
    base_url: str = "https://integrate.api.nvidia.com/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NVIDIA_",
        extra="ignore",
    )


settings = NVIDIASettings()
