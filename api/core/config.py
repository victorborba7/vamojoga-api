from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://vamojoga:vamojoga123@localhost:5432/vamojoga_db"

    # JWT
    SECRET_KEY: str = "change-me-in-env-file"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days

    # CORS — separe múltiplas origens por vírgula
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # App
    APP_NAME: str = "VamoJoga API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Resend
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "VamoJoga <noreply@vamojoga.com.br>"

    # Frontend URL for reset links
    FRONTEND_URL: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
