from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    VISA_SERVICE_URL: str
    MASTERCARD_SERVICE_URL: str
    APP_ENV: str = "development"

    class Config:
        env_file = ".env"


settings = Settings()
