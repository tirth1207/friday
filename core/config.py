from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_default_workspace() -> str:
    # Resolve repository root directory (parent of 'core')
    return str(Path(__file__).resolve().parent.parent)


class Settings(BaseSettings):
    friday_workspace: str = get_default_workspace()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FRIDAY_",
        extra="ignore",
    )


settings = Settings()
