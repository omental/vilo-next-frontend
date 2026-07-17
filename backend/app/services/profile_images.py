from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status


MAX_PROFILE_IMAGE_BYTES = 2 * 1024 * 1024
PROFILE_IMAGE_ROOT = Path("storage/profile_images")
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _detect_image_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _safe_relative_path(organization_id: int, user_id: int, filename: str) -> str:
    return f"profile_images/{int(organization_id)}/{int(user_id)}/{filename}"


def resolve_profile_image_path(relative_path: str | None) -> Path | None:
    if not relative_path:
        return None
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    if len(candidate.parts) != 4 or candidate.parts[0] != "profile_images":
        return None
    return Path("storage") / Path(*candidate.parts)


async def store_profile_image(*, organization_id: int, user_id: int, upload: UploadFile) -> tuple[str, Path | None]:
    content_type = (upload.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported image type")

    data = await upload.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty image")
    if len(data) > MAX_PROFILE_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Profile image exceeds 2MB limit")

    detected_type = _detect_image_type(data)
    if detected_type is None or detected_type != content_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image content does not match the declared type")

    ext = ALLOWED_IMAGE_TYPES[detected_type]
    relative_path = _safe_relative_path(organization_id, user_id, f"{uuid4().hex}.{ext}")
    file_path = resolve_profile_image_path(relative_path)
    if file_path is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid profile image path")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(data)
    return relative_path, file_path


def delete_profile_image(relative_path: str | None) -> None:
    file_path = resolve_profile_image_path(relative_path)
    if not file_path:
        return
    try:
        root = PROFILE_IMAGE_ROOT.resolve()
        resolved = file_path.resolve()
        if root not in resolved.parents:
            return
        if resolved.exists() and resolved.is_file():
            resolved.unlink()
    except OSError:
        return
