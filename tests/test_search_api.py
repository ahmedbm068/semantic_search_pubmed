"""API-level tests for the search endpoints."""
import pytest

from src.app.services.retriever import IndexUnavailable


class TestSearchGet:
    def test_returns_results(self, client, fake_index):
        r = client.get("/v1/search", params={"q": "diabetes", "k": 3})
        assert r.status_code == 200
        body = r.json()
        assert body["query"] == "diabetes"
        assert body["count"] == len(body["results"])
        assert body["count"] <= 3

    def test_response_shape(self, client, fake_index):
        hit = client.get("/v1/search", params={"q": "diabetes", "k": 1}).json()["results"][0]
        assert set(hit) == {"id", "score", "text", "meta"}

    @pytest.mark.parametrize("params", [
        {"q": ""},                 # empty query
        {"q": "x", "k": 0},        # k below minimum
        {"q": "x", "k": 100000},   # k above max_top_k
        {"q": "x", "min_score": 2},   # min_score out of range
        {"q": "x", "min_score": -1},
    ])
    def test_invalid_params_rejected(self, client, fake_index, params):
        assert client.get("/v1/search", params=params).status_code == 422

    def test_missing_query_rejected(self, client, fake_index):
        assert client.get("/v1/search").status_code == 422


class TestSearchPost:
    def test_returns_results(self, client, fake_index):
        r = client.post("/v1/search", json={"query": "asthma", "k": 2})
        assert r.status_code == 200
        assert r.json()["count"] <= 2

    def test_get_and_post_agree(self, client, fake_index):
        a = client.get("/v1/search", params={"q": "diabetes", "k": 3}).json()
        b = client.post("/v1/search", json={"query": "diabetes", "k": 3}).json()
        assert [h["id"] for h in a["results"]] == [h["id"] for h in b["results"]]

    def test_oversized_query_rejected(self, client, fake_index):
        assert client.post("/v1/search", json={"query": "x" * 5000}).status_code == 422


class TestErrorHandling:
    def test_missing_index_returns_503_with_actionable_message(
        self, client, monkeypatch
    ):
        from src.app.services.retriever import search_service

        def boom(*a, **kw):
            raise IndexUnavailable("FAISS index not found at /data/cache/faiss.index")

        monkeypatch.setattr(search_service, "search", boom)
        r = client.get("/v1/search", params={"q": "diabetes"})
        assert r.status_code == 503
        assert "not found" in r.json()["detail"]

    def test_unexpected_error_does_not_leak_internals(self, client, monkeypatch):
        from src.app.services.retriever import search_service

        def boom(*a, **kw):
            raise ValueError("/secret/path/on/disk exploded at line 42")

        monkeypatch.setattr(search_service, "search", boom)
        r = client.get("/v1/search", params={"q": "diabetes"})
        assert r.status_code == 500
        assert r.json()["detail"] == "Search failed"
        assert "secret" not in r.text


class TestStats:
    def test_reports_index_provenance(self, client, fake_index):
        body = client.get("/v1/search/stats").json()
        assert body["loaded"] is True
        assert body["documents"] == 4
        assert "index_built_with" in body
