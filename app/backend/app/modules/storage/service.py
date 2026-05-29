import io

from app.core.config import get_settings


class StorageService:
    def __init__(self):
        settings = get_settings()
        self._provider = (settings.storage_provider or "").lower()
        self._bucket_name = (
            settings.storage_bucket_name
            or settings.gcs_bucket
            or settings.s3_bucket_name
            or "dachjob-artifacts"
        )

        if not self._provider:
            self._provider = "s3"

        if self._provider == "gcs":
            self._init_gcs(settings)
        elif self._provider == "azure_blob":
            self._init_azure_blob(settings)
        else:
            self._init_s3(settings)

    def _init_gcs(self, settings) -> None:
        from google.cloud import storage

        self._gcs_client = storage.Client()
        self._gcs_bucket = self._gcs_client.bucket(self._bucket_name)

    def _init_s3(self, settings) -> None:
        import boto3
        from botocore.config import Config

        kwargs: dict = {
            "config": Config(signature_version="s3v4"),
            "region_name": settings.aws_region or "eu-west-1",
        }

        # Use explicit endpoint/creds only for local development (MinIO)
        use_local = (
            settings.app_env == "local"
            or (settings.s3_endpoint_url and "localhost" in settings.s3_endpoint_url)
        )
        if use_local:
            kwargs["endpoint_url"] = settings.s3_endpoint_url
            kwargs["aws_access_key_id"] = settings.s3_access_key_id
            kwargs["aws_secret_access_key"] = settings.s3_secret_access_key

        self._s3_client = boto3.client("s3", **kwargs)

    def _init_azure_blob(self, settings) -> None:
        from azure.storage.blob import BlobServiceClient

        self._blob_service = BlobServiceClient.from_connection_string(
            settings.azure_storage_connection_string
        )
        self._blob_container = self._blob_service.get_container_client(
            settings.azure_storage_container_name
        )

    def upload(self, key: str, body: bytes, content_type: str = "application/octet-stream") -> None:
        if self._provider == "gcs":
            blob = self._gcs_bucket.blob(key)
            blob.upload_from_file(io.BytesIO(body), content_type=content_type)
        elif self._provider == "azure_blob":
            from azure.storage.blob import ContentSettings

            self._blob_container.upload_blob(
                name=key,
                data=io.BytesIO(body),
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
        else:
            self._s3_client.put_object(
                Bucket=self._bucket_name,
                Key=key,
                Body=body,
                ContentType=content_type,
            )

    def download(self, key: str) -> bytes:
        if self._provider == "gcs":
            blob = self._gcs_bucket.blob(key)
            return blob.download_as_bytes()
        elif self._provider == "azure_blob":
            blob_client = self._blob_container.get_blob_client(key)
            return blob_client.download_blob().readall()
        else:
            response = self._s3_client.get_object(Bucket=self._bucket_name, Key=key)
            return response["Body"].read()

    def exists(self, key: str) -> bool:
        if self._provider == "gcs":
            blob = self._gcs_bucket.blob(key)
            return blob.exists()
        elif self._provider == "azure_blob":
            from azure.core.exceptions import ResourceNotFoundError

            try:
                self._blob_container.get_blob_client(key).get_blob_properties()
                return True
            except ResourceNotFoundError:
                return False
        else:
            try:
                self._s3_client.head_object(Bucket=self._bucket_name, Key=key)
                return True
            except Exception:
                return False
