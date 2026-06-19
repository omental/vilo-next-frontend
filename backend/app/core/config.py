from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/vilo"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 120
    app_base_url: str = "http://localhost:3000"
    public_backend_url: str | None = None
    onlyoffice_document_server_url: str | None = None
    onlyoffice_jwt_secret: str | None = None
    onlyoffice_file_token_expires_minutes: int = 15
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = "noreply@vilo.local"


settings = Settings()
