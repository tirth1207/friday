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
    # This is FRIDAY's private runtime/workspace root. Selected repositories are
    # cloned below it and developer tools are scoped to those clones.
    friday_workspace: str = get_default_workspace()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FRIDAY_",
        extra="ignore",
    )


settings = Settings()
