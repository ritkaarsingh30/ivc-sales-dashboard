"""
storage/base.py — Abstract storage backend
"""
from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    def get_file_bytes(self, relative_path: str) -> bytes:
        """Return raw bytes for a file by its relative path within the data folder."""
        ...

    @abstractmethod
    def list_files(self, folder: str) -> list[str]:
        """Return list of filenames in a folder."""
        ...

    @abstractmethod
    def exists(self, relative_path: str) -> bool:
        """Return True if the file exists."""
        ...
