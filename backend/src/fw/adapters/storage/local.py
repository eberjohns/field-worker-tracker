"""Local file storage adapter implementing FileStoragePort."""

import hashlib
from pathlib import Path
from typing import Protocol, runtime_checkable

import anyio
import structlog

from fw.core.config import get_settings

logger = structlog.get_logger(__name__)


@runtime_checkable
class FileStoragePort(Protocol):
    """Port for file storage (local disk, cloud bucket, etc.)."""

    async def save(self, relative_path: str, content: bytes) -> tuple[str, int, str]:
        """Save bytes to storage. Returns (file_ref, size_bytes, sha256_hash)."""
        ...

    async def read(self, file_ref: str) -> bytes:
        """Read bytes from storage."""
        ...

    async def exists(self, file_ref: str) -> bool:
        """Check if file exists."""
        ...

    async def delete(self, file_ref: str) -> bool:
        """Delete file if it exists."""
        ...

    def get_absolute_path(self, file_ref: str) -> str:
        """Return the physical filesystem path."""
        ...


class LocalStorageAdapter:
    """Stores files on the local filesystem."""

    def __init__(self, base_path: str | None = None) -> None:
        settings = get_settings()
        raw_path = base_path or settings.LOCAL_STORAGE_PATH
        p = Path(raw_path)
        if not p.is_absolute():
            # Anchor to repo root (parents[4] of backend/src/fw/adapters/storage/local.py)
            repo_root = Path(__file__).resolve().parents[4]
            self.base_dir = (repo_root / p).resolve()
        else:
            self.base_dir = p.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Fallback dir (backend/storage) in case server is executed from backend/
        backend_dir = Path(__file__).resolve().parents[3]
        self.fallback_dir = (backend_dir / "storage").resolve()
        self.fallback_dir.mkdir(parents=True, exist_ok=True)

    def _find_path(self, file_ref: str) -> Path | None:
        normalized_rel = file_ref.lstrip("/\\").replace("\\", "/")
        primary = (self.base_dir / normalized_rel).resolve()
        if primary.exists() and primary.is_file():
            return primary
        fallback = (self.fallback_dir / normalized_rel).resolve()
        if fallback.exists() and fallback.is_file():
            return fallback
        cwd_path = (Path.cwd() / "storage" / normalized_rel).resolve()
        if cwd_path.exists() and cwd_path.is_file():
            return cwd_path
        return None

    async def save(self, relative_path: str, content: bytes) -> tuple[str, int, str]:
        normalized_rel = relative_path.lstrip("/\\").replace("\\", "/")
        target_path = (self.base_dir / normalized_rel).resolve()
        # Security: ensure target_path is within base_dir
        if not str(target_path).startswith(str(self.base_dir)):
            raise ValueError(f"Target path {target_path} is outside base directory {self.base_dir}")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)

        # Also mirror to fallback_dir if distinct to guarantee discovery
        if self.fallback_dir != self.base_dir:
            fallback_target = (self.fallback_dir / normalized_rel).resolve()
            if str(fallback_target).startswith(str(self.fallback_dir)):
                fallback_target.parent.mkdir(parents=True, exist_ok=True)
                fallback_target.write_bytes(content)

        size_bytes = len(content)
        sha256_hash = hashlib.sha256(content).hexdigest()

        logger.info(
            "file_stored_locally",
            file_ref=normalized_rel,
            size_bytes=size_bytes,
            sha256=sha256_hash,
        )
        return normalized_rel, size_bytes, sha256_hash

    async def read(self, file_ref: str) -> bytes:
        found = self._find_path(file_ref)
        if not found:
            raise FileNotFoundError(f"File not found: {file_ref}")
        return found.read_bytes()

    async def exists(self, file_ref: str) -> bool:
        found = self._find_path(file_ref)
        return found is not None and found.is_file()

    async def delete(self, file_ref: str) -> bool:
        path_obj = Path(self.get_absolute_path(file_ref))

        def _do_unlink() -> bool:
            if path_obj.exists():
                path_obj.unlink()
                return True
            return False

        return await anyio.to_thread.run_sync(_do_unlink)

    def get_absolute_path(self, file_ref: str) -> str:
        normalized_rel = file_ref.lstrip("/\\").replace("\\", "/")
        target_path = (self.base_dir / normalized_rel).resolve()
        if not str(target_path).startswith(str(self.base_dir)):
            raise ValueError(f"Path traversal detected: {file_ref}")
        return str(target_path)


_storage_instance: FileStoragePort | None = None


def get_file_storage() -> FileStoragePort:
    """Return the configured file storage adapter."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = LocalStorageAdapter()
    return _storage_instance
