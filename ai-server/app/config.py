from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME:str = ""
    DATABASE_URL:str = ""
    OPENAI_API_KEY:str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding = "utf-8"
    )



@lru_cache
def get_settings()->Settings:
    return Settings()

settings = get_settings()