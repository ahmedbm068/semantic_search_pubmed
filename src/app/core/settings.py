from typing import List, Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, field_validator

class Settings(BaseSettings):
    app_env: str = "dev"
    secret_key: str = "change_me"
    access_token_expire_minutes: int = 60
    database_url: str = "sqlite+aiosqlite:///./app.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: List[Union[str, AnyHttpUrl]] = []
    rate_limit: str = "5/minute"

    embedding_model: Optional[str] = None
    index_path: Optional[str] = None
    emb_path: Optional[str] = None
    corpus_path: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    top_k: Optional[int] = None
    api_key_required: Optional[bool] = None
    jwt_secret: Optional[str] = None
    jwt_alg: str = "HS256"
    jwt_expire_minutes: Optional[int] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

settings = Settings()
