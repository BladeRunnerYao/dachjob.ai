import io

from google.cloud import storage

from app.core.config import get_settings


class StorageService:
    def __init__(self):
        settings = get_settings()
        self._s3_endpoint = settings.s3_endpoint_url
        self._use_gcs = "storage.googleapis.com" in settings.s3_endpoint_url
        self._bucket_name = settings.s3_bucket_name

        if self._use_gcs:
            self._gcs_client = storage.Client()
            self._gcs_bucket = self._gcs_client.bucket(self._bucket_name)
        else:
            import boto3
            from botocore.config import Config

            self._s3_client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key_id,
                aws_secret_access_key=settings.s3_secret_access_key,
                config=Config(signature_version="s3v4"),
                region_name="us-east-1",
            )

    def upload(self, key: str, body: bytes, content_type: str = "application/octet-stream") -> None:
        if self._use_gcs:
            blob = self._gcs_bucket.blob(key)
            blob.upload_from_file(io.BytesIO(body), content_type=content_type)
        else:
            self._s3_client.put_object(
                Bucket=self._bucket_name,
                Key=key,
                Body=body,
                ContentType=content_type,
            )

    def download(self, key: str) -> bytes:
        if self._use_gcs:
            blob = self._gcs_bucket.blob(key)
            return blob.download_as_bytes()
        else:
            response = self._s3_client.get_object(Bucket=self._bucket_name, Key=key)
            return response["Body"].read()

    def exists(self, key: str) -> bool:
        if self._use_gcs:
            blob = self._gcs_bucket.blob(key)
            return blob.exists()
        else:
            try:
                self._s3_client.head_object(Bucket=self._bucket_name, Key=key)
                return True
            except Exception:
                return False
