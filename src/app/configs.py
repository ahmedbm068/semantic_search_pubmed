from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    env: str = Field(default="dev")
    embedding_model: str = Field(default=str(ROOT_DIR / "models/biomed-miniLM"))
    index_path: str = Field(default=str(ROOT_DIR / "data/cache/faiss.index"))
    emb_path: str = Field(default=str(ROOT_DIR / "data/cache/embeddings.npy"))
    corpus_jsonl_path: str = Field(default=str(ROOT_DIR / "data/cache/corpus.jsonl"))
    corpus_pkl_path: str = Field(default=str(ROOT_DIR / "data/cache/corpus.pkl"))
    corpus_path: str = Field(default=str(ROOT_DIR / "data/cache/corpus.pkl"))
    chunk_size: int = Field(default=800)
    chunk_overlap: int = Field(default=120)
    top_k: int = Field(default=10)
    api_key_required: bool = Field(default=False)
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore", case_sensitive=False)

settings = Settings()
