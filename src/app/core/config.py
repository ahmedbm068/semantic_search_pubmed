"""Single source of truth for application configuration.

Replaces the previous split between ``core/settings.py`` (dead code) and
``configs.py`` (which declared ``env_prefix="APP_"`` while the shipped .env
used unprefixed keys, so every value in .env was silently ignored).
"""
from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


def _abs(p: str | Path) -> str:
    """Resolve a possibly-relative configured path against the project root."""
    p = Path(p)
    return str(p if p.is_absolute() else ROOT_DIR / p)


class Settings(BaseSettings):
    # ---- environment ----
    env: str = Field(default="dev")

    # ---- auth ----
    # No usable default: a hardcoded signing key lets anyone forge tokens.
    # Dev gets a random per-process key; prod refuses to boot without one set.
    jwt_secret: str = Field(default="")
    jwt_alg: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=60)

    # ---- storage ----
    database_url: str = Field(default="sqlite:///./data/app.db")
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ---- http ----
    # NoDecode: pydantic-settings would otherwise try to JSON-parse this from
    # .env and fail on a plain comma-separated string.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # ---- retrieval ----
    embedding_model: str = Field(default="models/biomed-miniLM")
    index_path: str = Field(default="data/cache/faiss.index")
    emb_path: str = Field(default="data/cache/embeddings.npy")
    corpus_jsonl_path: str = Field(default="data/cache/corpus.jsonl")
    top_k: int = Field(default=10)
    max_top_k: int = Field(default=100)

    # Hybrid retrieval: final = alpha * dense + (1 - alpha) * lexical.
    #
    # 0.5 is a deliberate compromise. On eval/eval_runner.py (200 queries) the
    # measured R@1 is: dense-only 0.64, alpha=0.7 0.81, alpha=0.5 0.89,
    # alpha=0.3 0.95, pure BM25 0.945 -- which would argue for a much more
    # lexical blend. But that benchmark's queries are verbatim sentences lifted
    # from their own gold documents, so it rewards keyword overlap and cannot
    # see the paraphrase robustness the dense side exists for. 0.5 keeps a real
    # dense contribution without tuning to a benchmark that is biased against it.
    hybrid_enabled: bool = Field(default=True)
    hybrid_alpha: float = Field(default=0.5, ge=0.0, le=1.0)
    hybrid_candidates: int = Field(default=100)

    # Cross-encoder reranking (off by default: adds latency + a model download).
    rerank_enabled: bool = Field(default=False)
    rerank_model: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    rerank_candidates: int = Field(default=50)

    # ---- chunking ----
    chunk_size: int = Field(default=800)
    chunk_overlap: int = Field(default=120)

    # ---- rate limiting (requests per window, seconds) ----
    rate_limit_times: int = Field(default=30)
    rate_limit_seconds: int = Field(default=60)

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", case_sensitive=False
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @model_validator(mode="after")
    def _check_secret(self):
        if not self.jwt_secret:
            if self.is_prod:
                raise ValueError(
                    "JWT_SECRET must be set when ENV=prod. "
                    "Generate one with: "
                    'python -c "import secrets;print(secrets.token_urlsafe(48))"'
                )
            # Dev fallback: random per process, so tokens simply don't survive a
            # restart. Never a shared constant that ships in source.
            object.__setattr__(self, "jwt_secret", secrets.token_urlsafe(48))
        return self

    @property
    def is_prod(self) -> bool:
        return self.env.lower() in {"prod", "production"}

    # Absolute-path accessors, so behaviour does not depend on the CWD the
    # server happens to be started from.
    @property
    def index_file(self) -> str:
        return _abs(self.index_path)

    @property
    def emb_file(self) -> str:
        return _abs(self.emb_path)

    @property
    def corpus_file(self) -> str:
        return _abs(self.corpus_jsonl_path)

    @property
    def model_dir(self) -> str:
        # A bare HuggingFace id (e.g. "sentence-transformers/all-MiniLM-L6-v2")
        # must be passed through untouched; only local paths get resolved.
        local = Path(_abs(self.embedding_model))
        return str(local) if local.exists() else self.embedding_model


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
