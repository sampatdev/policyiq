from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    anthropic_api_key: str = ""
    voyage_api_key: str = ""
    environment: str = "development"

    class Config:
        env_file = ".env"

settings = Settings()