from app.core.config import get_settings
from app.modules.storage.service import StorageService


def test_storage_service_uses_legacy_s3_bucket_env(monkeypatch):
    monkeypatch.delenv("STORAGE_BUCKET_NAME", raising=False)
    monkeypatch.delenv("GCS_BUCKET", raising=False)
    monkeypatch.setenv("S3_BUCKET_NAME", "cloud-artifacts")
    monkeypatch.setattr(StorageService, "_init_s3", lambda self, settings: None)
    get_settings.cache_clear()

    try:
        storage = StorageService()
    finally:
        get_settings.cache_clear()

    assert storage._bucket_name == "cloud-artifacts"


def test_storage_service_prefers_storage_bucket_env(monkeypatch):
    monkeypatch.setenv("STORAGE_BUCKET_NAME", "preferred-artifacts")
    monkeypatch.setenv("S3_BUCKET_NAME", "legacy-artifacts")
    monkeypatch.setattr(StorageService, "_init_s3", lambda self, settings: None)
    get_settings.cache_clear()

    try:
        storage = StorageService()
    finally:
        get_settings.cache_clear()

    assert storage._bucket_name == "preferred-artifacts"
