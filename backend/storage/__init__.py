from dotenv import load_dotenv
import os

load_dotenv()


def get_storage():
    backend = os.getenv("STORAGE_BACKEND", "local")
    if backend == "local":
        from .local import LocalStorage
        return LocalStorage()
    elif backend == "sheets":
        from .sheets import SheetStorage
        return SheetStorage()
    elif backend == "s3":
        from .s3 import S3Storage
        bucket = os.getenv("S3_BUCKET_NAME", "")
        return S3Storage(bucket)
    raise ValueError(f"Unknown STORAGE_BACKEND: {backend}")
