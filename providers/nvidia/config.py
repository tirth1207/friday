from pydantic_settings import BaseSettings, SettingsConfigDict


class NVIDIASettings(BaseSettings):
    api_key: str
    model: str
    base_url: str = "https://integrate.api.nvidia.com/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NVIDIA_",
    )


settings = NVIDIASettings()