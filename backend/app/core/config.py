from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Kiwoom API Settings
    KIWOOM_API_KEY: str
    KIWOOM_SECRET_KEY: str
    KIWOOM_ACCOUNT_ID: str
    KIWOOM_API_URL: str = "https://api.kiwoom.com:8443"
    KIWOOM_WS_URL: str = "wss://api.kiwoom.com:8443"

    # Security Settings
    SECURITY_SALT: str = "default_salt_for_dev_change_me"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
