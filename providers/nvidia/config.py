from pydantic_settings import BaseSettings, SettingsConfigDict


class NVIDIASettings(BaseSettings):
    api_key: str = "mock_key_for_dev"
    # Nemotron 3 Super is currently documented by NVIDIA as an agentic/tool-calling
    # model and is available through the free hosted endpoint.
    model: str = "nvidia/nemotron-3-super-120b-a12b"
    base_url: str = "https://integrate.api.nvidia.com/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NVIDIA_",
        extra="ignore",
    )


settings = NVIDIASettings()
