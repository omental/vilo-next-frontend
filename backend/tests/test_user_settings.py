from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import AsyncIterator

from fastapi.testclient import TestClient

from app.api import deps as deps_module
from app.core.security import hash_password, verify_password
from app.main import app
from app.models.enums import RecordStatus, UserRole


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 32


class UserSettingsDBStub:
    def __init__(self, user):
        self.user = user
        self.commits = 0

    async def scalar(self, *args, **kwargs):
        return "Acme Law"

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        return None


def user_obj(user_id=2, org_id=1, password="secret123"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=user_id,
        organization_id=org_id,
        name="Settings User",
        email="settings@example.com",
        hashed_password=hash_password(password),
        role=UserRole.lawyer,
        status=RecordStatus.active,
        profile_image_path=None,
        profile_image_updated_at=None,
        created_at=now,
        updated_at=now,
    )


def build_client(db: UserSettingsDBStub, user):
    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator[UserSettingsDBStub]:
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db
    return TestClient(app)


def cleanup(client: TestClient):
    client.close()
    app.dependency_overrides.clear()


def test_authenticated_user_reads_own_profile():
    user = user_obj()
    db = UserSettingsDBStub(user)
    client = build_client(db, user)
    try:
        res = client.get("/api/v1/users/me")
        assert res.status_code == 200
        body = res.json()
        assert body["email"] == "settings@example.com"
        assert body["role"] == "lawyer"
        assert body["organization_name"] == "Acme Law"
        assert "hashed_password" not in body
    finally:
        cleanup(client)


def test_unauthenticated_profile_request_is_rejected():
    client = TestClient(app)
    try:
        res = client.get("/api/v1/users/me")
        assert res.status_code == 401
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_user_updates_permitted_own_fields_only():
    user = user_obj()
    db = UserSettingsDBStub(user)
    client = build_client(db, user)
    try:
        res = client.patch("/api/v1/users/me", json={"name": "Updated Name", "role": "partner", "organization_id": 999, "status": "inactive"})
        assert res.status_code == 200
        body = res.json()
        assert body["name"] == "Updated Name"
        assert body["role"] == "lawyer"
        assert body["organization_id"] == 1
        assert body["status"] == "active"
    finally:
        cleanup(client)


def test_current_password_required_and_incorrect_password_rejected():
    user = user_obj(password="secret123")
    db = UserSettingsDBStub(user)
    client = build_client(db, user)
    try:
        missing = client.post("/api/v1/users/me/password", json={"new_password": "newsecret123", "confirm_password": "newsecret123"})
        assert missing.status_code == 422
        wrong = client.post("/api/v1/users/me/password", json={"current_password": "wrongpass", "new_password": "newsecret123", "confirm_password": "newsecret123"})
        assert wrong.status_code == 400
    finally:
        cleanup(client)


def test_new_password_is_hashed_and_plaintext_is_never_returned():
    user = user_obj(password="secret123")
    db = UserSettingsDBStub(user)
    client = build_client(db, user)
    try:
        res = client.post("/api/v1/users/me/password", json={"current_password": "secret123", "new_password": "newsecret123", "confirm_password": "newsecret123"})
        assert res.status_code == 200
        assert verify_password("newsecret123", user.hashed_password)
        assert user.hashed_password != "newsecret123"
        assert "newsecret123" not in res.text
    finally:
        cleanup(client)


def test_profile_picture_upload_replace_and_remove(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    user = user_obj()
    db = UserSettingsDBStub(user)
    client = build_client(db, user)
    try:
        first = client.post("/api/v1/users/me/profile-picture", files={"file": ("avatar.png", PNG_BYTES, "image/png")})
        assert first.status_code == 200
        first_path = tmp_path / "storage" / user.profile_image_path
        assert first_path.exists()

        second = client.post("/api/v1/users/me/profile-picture", files={"file": ("avatar.jpg", JPEG_BYTES, "image/jpeg")})
        assert second.status_code == 200
        assert not first_path.exists()
        second_path = tmp_path / "storage" / user.profile_image_path
        assert second_path.exists()

        image = client.get("/api/v1/users/me/profile-picture")
        assert image.status_code == 200
        assert image.headers["content-type"].startswith("image/jpeg")

        removed = client.delete("/api/v1/users/me/profile-picture")
        assert removed.status_code == 200
        assert user.profile_image_path is None
        assert not second_path.exists()
    finally:
        cleanup(client)


def test_profile_picture_rejects_unsupported_oversized_and_spoofed_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    user = user_obj()
    db = UserSettingsDBStub(user)
    client = build_client(db, user)
    try:
        unsupported = client.post("/api/v1/users/me/profile-picture", files={"file": ("avatar.gif", b"GIF89a", "image/gif")})
        assert unsupported.status_code == 400
        oversized = client.post("/api/v1/users/me/profile-picture", files={"file": ("avatar.png", PNG_BYTES + b"0" * (2 * 1024 * 1024), "image/png")})
        assert oversized.status_code == 400
        spoofed = client.post("/api/v1/users/me/profile-picture", files={"file": ("avatar.png", b"not-a-png", "image/png")})
        assert spoofed.status_code == 400
    finally:
        cleanup(client)


def test_no_endpoint_allows_user_to_change_another_users_picture():
    user = user_obj()
    db = UserSettingsDBStub(user)
    client = build_client(db, user)
    try:
        res = client.post("/api/v1/users/999/profile-picture", files={"file": ("avatar.png", PNG_BYTES, "image/png")})
        assert res.status_code in {404, 405}
    finally:
        cleanup(client)
