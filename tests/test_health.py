"""Health and readiness endpoints."""


class TestHealth:
    def test_root_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_versioned_health(self, client):
        r = client.get("/v1/health")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_health_does_not_load_the_index(self, client):
        """Liveness must stay fast: loading 200MB on a probe is a startup stall."""
        from src.app.services.retriever import search_service

        was_loaded = search_service.is_loaded
        client.get("/health")
        assert search_service.is_loaded == was_loaded


class TestReadiness:
    def test_reports_index_state(self, client):
        r = client.get("/v1/ready")
        assert r.status_code == 200
        assert "index_loaded" in r.json()
