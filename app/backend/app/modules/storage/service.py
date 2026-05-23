import boto3
from botocore.config import Config

from app.core.config import get_settings


class StorageService:
    def __init__(self):
        settings = get_settings()
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self.bucket = settings.s3_bucket_name

    def upload(self, key: str, body: bytes, content_type: str = "application/octet-stream") -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    def download(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False
