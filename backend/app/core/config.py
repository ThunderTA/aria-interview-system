from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "aria"

    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    cors_origins: str = "http://localhost:5173"

    # LLM engine. Defaults to a local Ollama server so the project needs no API
    # key and runs offline; point llm_base_url at any OpenAI-compatible endpoint
    # to swap providers.
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:7b"
    llm_timeout_seconds: float = 120.0

    # Speech-to-text. Runs locally via faster-whisper; no API key, no upload.
    # "small" over "base" because transcription errors feed straight into the
    # LLM's score — a misheard technical term costs the candidate real marks.
    whisper_model: str = "small"
    whisper_compute_type: str = "int8"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
