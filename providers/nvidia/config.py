from pydantic_settings import BaseSettings, SettingsConfigDict


class NVIDIASettings(BaseSettings):
    # Empty by default so a missing .env cannot silently become a fake credential.
    api_key: str = ""
    model: str = "nvidia/nemotron-3-super-120b-a12b"
    base_url: str = "https://integrate.api.nvidia.com/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NVIDIA_",
        extra="ignore",
    )


settings = NVIDIASettings()
