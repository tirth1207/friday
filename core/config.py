import os
import platform
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def get_default_workspace() -> str:
    """Return FRIDAY's private runtime directory, never the FRIDAY source tree."""
    configured = os.getenv("FRIDAY_WORKSPACE")
    if configured:
        return str(Path(configured).expanduser().resolve())

    if platform.system() == "Windows":
        return r"C:\.friday"

    return str((Path.home() / ".friday").resolve())


class Settings(BaseSettings):
    friday_workspace: str = get_default_workspace()

    proactive_enabled: bool = True
    proactive_cognition_enabled: bool = True
    proactive_cognition_interval_seconds: int = 3600
    proactive_initial_delay_seconds: int = 60

    proactive_osiris_enabled: bool = True
    proactive_osiris_interval_seconds: int = 900

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FRIDAY_",
        extra="ignore",
    )


settings = Settings()
