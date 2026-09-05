"""GitHub credential settings for FRIDAY."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class GitHubSettings(BaseSettings):
    username: str = ""
    pat: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GITHUB_",
        extra="ignore",
    )


settings = GitHubSettings()
