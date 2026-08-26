"""Shared test fixtures.

Deliberately avoids loading the real FAISS index or transformer: that costs
~15s and 200MB, and none of the API-level behaviour under test depends on the
actual model. Retrieval logic itself is tested directly in test_retriever.py.
"""
import os
import tempfile

import pytest

# Must be set before src.app.core.config is imported anywhere.
os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-used-in-production")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/15")


@pytest.fixture(scope="session")
def _db_path():
    fd, path = tempfile.mkstemp(suffix=".db", prefix="pubmed_test_")
    os.close(fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture(scope="session")
def app(_db_path):
    from src.app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient

    # Session-scoped: the lifespan attempts a Redis connection, and paying that
    # timeout once per test made the suite ~70s instead of ~7s. Tests generate
    # unique emails, so sharing the client does not couple them.
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def fake_index(monkeypatch):
    """Swap the retriever's heavy internals for a tiny in-memory corpus."""
    from src.app.services.lexical import BM25Index
    from src.app.services.retriever import search_service

    corpus = [
        {"id": 0, "text": "Metformin is a first line therapy for type 2 diabetes mellitus."},
        {"id": 1, "text": "Inhaled corticosteroids reduce asthma exacerbations in adults."},
        {"id": 2, "text": "Statins lower LDL cholesterol and cardiovascular risk."},
        {"id": 3, "text": "Insulin glargine provides basal glycemic control in diabetes."},
    ]

    class _StubModel:
        def get_sentence_embedding_dimension(self):
            return 4

        def encode(self, texts, **kwargs):
            import numpy as np

            return np.ones((len(texts), 4), dtype="float32")

    class _StubIndex:
        d = 4
        ntotal = len(corpus)

        def search(self, vec, k):
            import numpy as np

            k = min(k, self.ntotal)
            ids = np.arange(k, dtype="int64")[None, :]
            scores = np.linspace(0.9, 0.1, k, dtype="float32")[None, :]
            return scores, ids

    monkeypatch.setattr(search_service, "_corpus", corpus, raising=False)
    monkeypatch.setattr(search_service, "_index", _StubIndex(), raising=False)
    monkeypatch.setattr(search_service, "_model", _StubModel(), raising=False)
    monkeypatch.setattr(
        search_service, "_bm25", BM25Index().fit([d["text"] for d in corpus]), raising=False
    )
    monkeypatch.setattr(search_service, "_meta", {"model_path": "stub"}, raising=False)
    monkeypatch.setattr(search_service, "_loaded", True, raising=False)
    yield search_service
    monkeypatch.setattr(search_service, "_loaded", False, raising=False)


@pytest.fixture()
def auth_headers(client):
    """Register a unique user and return an Authorization header for it."""
    import uuid

    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "correct-horse-battery"
    r = client.post(
        "/v1/auth/register",
        json={"email": email, "username": "tester", "password": password},
    )
    assert r.status_code == 201, r.text
    r = client.post("/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
