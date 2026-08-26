"""Configuration and security-default tests."""
import pytest

from src.app.core.config import Settings
from src.app.db.session import _sync_url


class TestSecretHandling:
    def test_production_refuses_to_boot_without_a_secret(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET", raising=False)
        with pytest.raises(ValueError, match="JWT_SECRET"):
            Settings(env="prod", jwt_secret="", _env_file=None)

    def test_dev_generates_an_ephemeral_secret(self):
        s = Settings(env="dev", jwt_secret="", _env_file=None)
        assert len(s.jwt_secret) >= 32

    def test_generated_secrets_differ_between_instances(self):
        a = Settings(env="dev", jwt_secret="", _env_file=None)
        b = Settings(env="dev", jwt_secret="", _env_file=None)
        assert a.jwt_secret != b.jwt_secret

    def test_no_hardcoded_default_secret_in_source(self):
        """Regression guard for the old `SECRET_KEY = "change_me_please"`."""
        from pathlib import Path

        src = Path(__file__).resolve().parents[1] / "src" / "app"
        offenders = [
            p for p in src.rglob("*.py")
            if "change_me" in p.read_text(encoding="utf-8")
        ]
        assert offenders == []


class TestCorsParsing:
    def test_comma_separated_string_becomes_list(self):
        s = Settings(cors_origins="http://a.com, http://b.com", _env_file=None)
        assert s.cors_origins == ["http://a.com", "http://b.com"]

    def test_empty_string_is_empty_list(self):
        assert Settings(cors_origins="", _env_file=None).cors_origins == []


class TestDatabaseUrlNormalisation:
    @pytest.mark.parametrize("given,expected", [
        ("sqlite+aiosqlite:///./app.db", "sqlite:///./app.db"),
        ("sqlite:///./app.db", "sqlite:///./app.db"),
        ("postgresql+asyncpg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ])
    def test_async_drivers_are_downgraded_to_sync(self, given, expected):
        assert _sync_url(given) == expected


class TestPathResolution:
    def test_relative_paths_resolve_against_project_root(self):
        s = Settings(index_path="data/cache/faiss.index", _env_file=None)
        assert s.index_file.replace("\\", "/").endswith("data/cache/faiss.index")

    def test_huggingface_ids_are_not_treated_as_paths(self):
        s = Settings(embedding_model="sentence-transformers/all-MiniLM-L6-v2", _env_file=None)
        assert s.model_dir == "sentence-transformers/all-MiniLM-L6-v2"
