import os
import re
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status


ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "jpg", "jpeg", "png", "txt"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def safe_original_name(original: str) -> str:
    name = os.path.basename((original or "").strip())
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file name")
    return name


def validate_extension(file_name: str, allowed_extensions: set[str] | None = None) -> str:
    parts = file_name.rsplit(".", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File extension is required")
    ext = parts[1].lower()
    allowed = allowed_extensions or ALLOWED_EXTENSIONS
    if ext not in allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")
    return ext


def persist_file(storage_root: Path, organization_id: int, original_name: str, data: bytes) -> tuple[str, str]:
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File exceeds upload size limit")

    ext = validate_extension(original_name)
    org_dir = storage_root / str(organization_id)
    org_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}.{ext}"
    file_path = org_dir / stored_name
    file_path.write_bytes(data)
    return str(file_path), stored_name


def build_text_filename(name: str, fallback_stem: str = "document") -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", (name or "").strip()).strip("-.")
    if not stem:
        stem = fallback_stem
    if "." in stem:
        stem = stem.rsplit(".", 1)[0]
    return f"{stem}.txt"
