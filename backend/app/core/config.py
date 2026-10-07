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

    # Candidate identity verification (face embeddings). See
    # app/services/face_identity.py for the models and identity_service.py for
    # how checks become a verdict. Similarities are cosine, on SFace embeddings.
    identity_verification_enabled: bool = True
    # Fernet key for embeddings at rest. Empty means "derive one from
    # jwt_secret" — fine locally, but set a dedicated key anywhere shared so
    # rotating the JWT secret doesn't also invalidate stored references.
    face_embedding_key: str = ""
    identity_detection_score: float = 0.80
    # OpenCV's published SFace threshold. A resume photo is often old, small
    # and compressed, so this is the more forgiving of the two.
    identity_resume_match_threshold: float = 0.363
    # Webcam against a reference captured by the same webcam minutes earlier:
    # conditions barely change, so this can afford to be stricter.
    identity_camera_match_threshold: float = 0.42
    identity_min_face_px_resume: int = 36
    identity_min_face_px_live: int = 60
    # A second face smaller than this fraction of the main one (a poster, a
    # photo on the wall) is ignored rather than counted as another person.
    identity_secondary_face_ratio: float = 0.35
    identity_min_brightness: float = 35.0
    identity_min_sharpness: float = 15.0
    identity_check_interval_seconds: int = 15
    identity_mismatch_streak_to_flag: int = 3
    identity_multi_face_streak_to_flag: int = 2
    identity_start_max_attempts: int = 3
    identity_allow_continue_unmatched: bool = True
    identity_verified_min_match_rate: float = 0.8
    identity_min_conclusive_checks: int = 2
    # Share of the expected periodic checks that must actually arrive; fewer
    # means the checks were blocked or the camera was off for long stretches.
    identity_min_check_coverage: float = 0.5
    identity_resume_reference_ttl_days: int = 30
    identity_session_reference_ttl_hours: int = 6
    identity_resume_analysis_timeout_seconds: float = 30.0

    # Conversational interview. The interviewer's voice is Kokoro, a local
    # neural TTS (app/services/tts.py); the browser's own voice is the fallback.
    tts_enabled: bool = True
    tts_voice: str = "af_heart"
    tts_speed: float = 1.0
    # Past two follow-ups on one question, a conversation starts to feel like
    # an interrogation.
    conversation_max_follow_ups: int = 2
    conversation_max_clarifications: int = 2

    # Live attention readout — where the candidate is looking, sampled from the
    # camera while the interview runs. The gaze angles themselves live in
    # cv_analysis.py, next to the geometry they describe.
    attention_checks_enabled: bool = True
    attention_check_interval_seconds: int = 4
    # Consecutive off-camera checks before it's worth mentioning: four at the
    # default interval is about a quarter of a minute of looking elsewhere.
    attention_away_streak_to_flag: int = 4

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
