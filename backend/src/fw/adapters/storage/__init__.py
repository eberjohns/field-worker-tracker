"""Storage adapters."""

from fw.adapters.storage.local import FileStoragePort, LocalStorageAdapter, get_file_storage

__all__ = ["FileStoragePort", "LocalStorageAdapter", "get_file_storage"]
