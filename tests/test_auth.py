"""Auth and access-control tests."""
import uuid
from datetime import UTC


def _new_email():
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


class TestRegistration:
    def test_creates_user(self, client):
        r = client.post(
            "/v1/auth/register",
            json={"email": _new_email(), "username": "a", "password": "secret123"},
        )
        assert r.status_code == 201
        assert "id" in r.json()

    def test_password_is_not_echoed(self, client):
        r = client.post(
            "/v1/auth/register",
            json={"email": _new_email(), "username": "a", "password": "secret123"},
        )
        assert "secret123" not in r.text
        assert "password" not in r.json()

    def test_duplicate_email_rejected(self, client):
        email = _new_email()
        body = {"email": email, "username": "a", "password": "secret123"}
        assert client.post("/v1/auth/register", json=body).status_code == 201
        assert client.post("/v1/auth/register", json=body).status_code == 400

    def test_email_is_normalised_to_lowercase(self, client):
        email = _new_email()
        client.post(
            "/v1/auth/register",
            json={"email": email.upper(), "username": "a", "password": "secret123"},
        )
        # Registering the lowercase form must now collide.
        r = client.post(
            "/v1/auth/register",
            json={"email": email, "username": "a", "password": "secret123"},
        )
        assert r.status_code == 400

    def test_malformed_email_rejected(self, client):
        r = client.post(
            "/v1/auth/register",
            json={"email": "not-an-email", "username": "a", "password": "secret123"},
        )
        assert r.status_code == 422


class TestLogin:
    def test_returns_bearer_token(self, client):
        email = _new_email()
        client.post(
            "/v1/auth/register",
            json={"email": email, "username": "a", "password": "secret123"},
        )
        r = client.post("/v1/auth/login", data={"username": email, "password": "secret123"})
        assert r.status_code == 200
        assert r.json()["token_type"] == "bearer"
        assert r.json()["access_token"]

    def test_wrong_password_rejected(self, client):
        email = _new_email()
        client.post(
            "/v1/auth/register",
            json={"email": email, "username": "a", "password": "secret123"},
        )
        r = client.post("/v1/auth/login", data={"username": email, "password": "wrong"})
        assert r.status_code == 401

    def test_unknown_user_rejected(self, client):
        r = client.post(
            "/v1/auth/login", data={"username": _new_email(), "password": "secret123"}
        )
        assert r.status_code == 401

    def test_error_does_not_reveal_which_field_was_wrong(self, client):
        """Distinct messages for unknown-user vs bad-password enable enumeration."""
        email = _new_email()
        client.post(
            "/v1/auth/register",
            json={"email": email, "username": "a", "password": "secret123"},
        )
        bad_pw = client.post("/v1/auth/login", data={"username": email, "password": "x"})
        no_user = client.post(
            "/v1/auth/login", data={"username": _new_email(), "password": "x"}
        )
        assert bad_pw.json()["detail"] == no_user.json()["detail"]


class TestProtectedRoutes:
    def test_me_requires_token(self, client):
        assert client.get("/v1/auth/me").status_code == 401

    def test_me_rejects_garbage_token(self, client):
        r = client.get("/v1/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
        assert r.status_code == 401

    def test_me_returns_current_user(self, client, auth_headers):
        r = client.get("/v1/auth/me", headers=auth_headers)
        assert r.status_code == 200
        assert "@" in r.json()["email"]

    def test_token_signed_with_other_key_is_rejected(self, client):
        from datetime import datetime, timedelta

        from jose import jwt

        forged = jwt.encode(
            {"sub": "attacker@example.com", "exp": datetime.now(UTC) + timedelta(hours=1)},
            "change_me_please",  # the old hardcoded key
            algorithm="HS256",
        )
        r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
        assert r.status_code == 401

    def test_expired_token_is_rejected(self, client, auth_headers):
        from datetime import datetime, timedelta

        from jose import jwt

        from src.app.core.config import settings

        expired = jwt.encode(
            {"sub": "x@example.com", "exp": datetime.now(UTC) - timedelta(minutes=1)},
            settings.jwt_secret,
            algorithm=settings.jwt_alg,
        )
        r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
        assert r.status_code == 401


class TestIngestAuth:
    def test_ingest_requires_authentication(self, client):
        r = client.post("/v1/ingest/web", json={"docs": []})
        assert r.status_code == 401


class TestChatIsolation:
    def test_conversations_require_auth(self, client):
        assert client.get("/v1/chat/conversations").status_code == 401

    def test_user_cannot_read_another_users_conversation(self, client):
        first = client.post("/v1/auth/register", json={
            "email": _new_email(), "username": "a", "password": "secret123"})
        assert first.status_code == 201

        def headers_for(email):
            client.post("/v1/auth/register",
                        json={"email": email, "username": "u", "password": "secret123"})
            tok = client.post("/v1/auth/login",
                              data={"username": email, "password": "secret123"}).json()
            return {"Authorization": f"Bearer {tok['access_token']}"}

        alice = headers_for(_new_email())
        bob = headers_for(_new_email())

        convo = client.post("/v1/chat/conversations", json={"title": "private"}, headers=alice)
        assert convo.status_code == 201
        cid = convo.json()["id"]

        assert client.get(f"/v1/chat/conversations/{cid}", headers=alice).status_code == 200
        assert client.get(f"/v1/chat/conversations/{cid}", headers=bob).status_code == 404
        assert client.delete(f"/v1/chat/conversations/{cid}", headers=bob).status_code == 404
