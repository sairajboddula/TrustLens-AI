"""
File Utilities

Helpers for uploading, hashing, and validating files used in the KYC
document upload flow.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from typing import Optional, Tuple

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Allowed MIME types and extensions whitelist
# ---------------------------------------------------------------------------

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "application/pdf",
}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}

# Maximum file size: 10 MB (default, overridable per call)
DEFAULT_MAX_SIZE_MB = 10


# ---------------------------------------------------------------------------
# File saving
# ---------------------------------------------------------------------------


async def save_uploaded_file(file, upload_dir: str) -> Tuple[str, str]:
    """
    Persist an uploaded FastAPI UploadFile to *upload_dir* using a UUID
    filename to prevent collisions and avoid directory-traversal attacks.

    Args:
        file:       FastAPI UploadFile instance.
        upload_dir: Absolute path to the upload directory.

    Returns:
        Tuple of (stored_filename: str, full_storage_path: str).

    Raises:
        OSError: If the directory cannot be created or the file cannot be written.
    """
    os.makedirs(upload_dir, exist_ok=True)

    original_name = file.filename or "unknown"
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".bin"

    stored_filename = f"{uuid.uuid4()}{ext}"
    storage_path = os.path.join(upload_dir, stored_filename)

    try:
        content = await file.read()
        with open(storage_path, "wb") as f:
            f.write(content)
    finally:
        # Reset file pointer so callers can re-read if needed
        await file.seek(0)

    logger.debug(
        "File saved",
        original_name=original_name,
        stored_name=stored_filename,
        size_bytes=os.path.getsize(storage_path),
    )
    return stored_filename, storage_path


def save_file_sync(content: bytes, upload_dir: str, ext: str = ".bin") -> Tuple[str, str]:
    """
    Synchronous variant: save raw bytes to upload_dir.

    Returns:
        Tuple of (stored_filename, full_storage_path).
    """
    os.makedirs(upload_dir, exist_ok=True)
    stored_filename = f"{uuid.uuid4()}{ext}"
    storage_path = os.path.join(upload_dir, stored_filename)
    with open(storage_path, "wb") as f:
        f.write(content)
    return stored_filename, storage_path


# ---------------------------------------------------------------------------
# File hashing
# ---------------------------------------------------------------------------


def get_file_hash(file_path: str) -> str:
    """
    Compute the SHA-256 hash of a file.

    Reads in 64 KB chunks to handle large files without loading entirely
    into memory.

    Args:
        file_path: Absolute path to the file.

    Returns:
        Hex-encoded SHA-256 digest string (64 characters).

    Raises:
        FileNotFoundError: If *file_path* does not exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    sha256 = hashlib.sha256()
    chunk_size = 65_536  # 64 KB

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)

    return sha256.hexdigest()


def get_bytes_hash(content: bytes) -> str:
    """Return SHA-256 hex digest of *content* bytes."""
    return hashlib.sha256(content).hexdigest()


# ---------------------------------------------------------------------------
# File type validation
# ---------------------------------------------------------------------------


def validate_file_type(
    filename: str,
    content_type: Optional[str],
) -> Tuple[bool, Optional[str]]:
    """
    Validate a file against the MIME-type and extension whitelist.

    Both the content-type header *and* the file extension must be in the
    allowed sets.  This prevents cases where a malicious file uses an
    allowed content-type but has a dangerous extension (or vice-versa).

    Args:
        filename:     Original filename (used to check extension).
        content_type: MIME type reported by the client.

    Returns:
        (is_valid: bool, error_message: str | None)
    """
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        return False, (
            f"File extension '{ext}' is not allowed. "
            f"Allowed: {sorted(ALLOWED_EXTENSIONS)}"
        )

    if content_type and content_type.lower() not in ALLOWED_MIME_TYPES:
        return False, (
            f"Content type '{content_type}' is not allowed. "
            f"Allowed: {sorted(ALLOWED_MIME_TYPES)}"
        )

    return True, None


# ---------------------------------------------------------------------------
# File size validation
# ---------------------------------------------------------------------------


def validate_file_size(
    file_path: str,
    max_size_mb: float = DEFAULT_MAX_SIZE_MB,
) -> Tuple[bool, Optional[str]]:
    """
    Check that a file does not exceed *max_size_mb*.

    Args:
        file_path:   Absolute path to the file.
        max_size_mb: Maximum allowed size in megabytes.

    Returns:
        (is_valid: bool, error_message: str | None)
    """
    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}"

    size_bytes = os.path.getsize(file_path)
    max_bytes = max_size_mb * 1024 * 1024

    if size_bytes > max_bytes:
        size_mb = size_bytes / (1024 * 1024)
        return False, (
            f"File size {size_mb:.2f} MB exceeds the maximum allowed "
            f"size of {max_size_mb} MB."
        )

    return True, None


def validate_file_size_bytes(
    content: bytes,
    max_size_mb: float = DEFAULT_MAX_SIZE_MB,
) -> Tuple[bool, Optional[str]]:
    """
    Validate size of raw bytes content.

    Returns:
        (is_valid: bool, error_message: str | None)
    """
    max_bytes = max_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        size_mb = len(content) / (1024 * 1024)
        return False, (
            f"File size {size_mb:.2f} MB exceeds the maximum allowed "
            f"size of {max_size_mb} MB."
        )
    return True, None
