"""
storage/s3.py — AWS S3 storage stub

# TODO: implement with boto3 when AWS migration begins
"""
from .base import StorageBackend


class S3Storage(StorageBackend):
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name

    def get_file_bytes(self, relative_path: str) -> bytes:
        raise NotImplementedError("S3 storage not yet configured. Set STORAGE_BACKEND=local.")

    def list_files(self, folder: str) -> list[str]:
        raise NotImplementedError("S3 storage not yet configured. Set STORAGE_BACKEND=local.")

    def exists(self, relative_path: str) -> bool:
        raise NotImplementedError("S3 storage not yet configured. Set STORAGE_BACKEND=local.")
