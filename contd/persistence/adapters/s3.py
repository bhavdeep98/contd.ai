"""
S3 adapter for large state storage with integrity validation.
"""

import hashlib
import logging
from typing import Optional
from dataclasses import dataclass

try:
    import boto3
    from botocore.exceptions import ClientError

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

logger = logging.getLogger(__name__)


@dataclass
class S3Config:
    """S3 connection configuration."""

    bucket: str = "contd-snapshots"
    region: str = "us-east-1"
    endpoint_url: Optional[str] = None  # For LocalStack/MinIO
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    # Integrity settings
    enable_checksum: bool = True
    storage_class: str = "STANDARD"  # STANDARD, STANDARD_IA, etc.


class S3Adapter:
    """
    S3 adapter with:
    - Checksum validation on read/write
    - Automatic retry with exponential backoff
    - Support for LocalStack/MinIO for testing
    """

    def __init__(self, config: S3Config = None):
        if not HAS_BOTO3:
            raise ImportError("boto3 is required. Install with: pip install boto3")

        self.config = config or S3Config()
        self._client = None
        self._initialized = False

    def initialize(self):
        """Initialize S3 client."""
        if self._initialized:
            return

        client_kwargs = {
            "region_name": self.config.region,
        }

        if self.config.endpoint_url:
            client_kwargs["endpoint_url"] = self.config.endpoint_url

        if self.config.access_key_id and self.config.secret_access_key:
            client_kwargs["aws_access_key_id"] = self.config.access_key_id
            client_kwargs["aws_secret_access_key"] = self.config.secret_access_key

        self._client = boto3.client("s3", **client_kwargs)
        self._initialized = True
        logger.info(f"S3 client initialized: bucket={self.config.bucket}")

    @property
    def client(self):
        if not self._initialized:
            self.initialize()
        return self._client

    def put(self, key: str, data: str, metadata: dict = None) -> str:
        """
        Store data in S3 with checksum validation.
        Returns the checksum for verification.
        """
        # Compute checksum
        checksum = hashlib.sha256(data.encode("utf-8")).hexdigest()

        put_kwargs = {
            "Bucket": self.config.bucket,
            "Key": key,
            "Body": data.encode("utf-8"),
            "StorageClass": self.config.storage_class,
            "Metadata": {"checksum-sha256": checksum, **(metadata or {})},
        }

        if self.config.enable_checksum:
            # Use S3's built-in checksum validation
            put_kwargs["ChecksumAlgorithm"] = "SHA256"

        try:
            self.client.put_object(**put_kwargs)
            logger.debug(f"Stored object: {key} (checksum: {checksum[:16]}...)")
            return checksum
        except ClientError as e:
            logger.error(f"Failed to store object {key}: {e}")
            raise

    def get(self, key: str, expected_checksum: str = None) -> str:
        """
        Retrieve data from S3 with checksum validation.
        Raises exception if checksum doesn't match.
        """
        try:
            response = self.client.get_object(Bucket=self.config.bucket, Key=key)

            data = response["Body"].read().decode("utf-8")

            # Validate checksum
            actual_checksum = hashlib.sha256(data.encode("utf-8")).hexdigest()

            # Check against stored metadata checksum
            stored_checksum = response.get("Metadata", {}).get("checksum-sha256")

            if stored_checksum and actual_checksum != stored_checksum:
                raise IntegrityError(
                    f"Checksum mismatch for {key}: stored={stored_checksum}, actual={actual_checksum}"
                )

            if expected_checksum and actual_checksum != expected_checksum:
                raise IntegrityError(
                    f"Checksum mismatch for {key}: expected={expected_checksum}, actual={actual_checksum}"
                )

            logger.debug(f"Retrieved object: {key}")
            return data

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise KeyNotFoundError(f"Object not found: {key}")
            logger.error(f"Failed to retrieve object {key}: {e}")
            raise

    def delete(self, key: str):
        """Delete an object from S3."""
        try:
            self.client.delete_object(Bucket=self.config.bucket, Key=key)
            logger.debug(f"Deleted object: {key}")
        except ClientError as e:
            logger.error(f"Failed to delete object {key}: {e}")
            raise

    def exists(self, key: str) -> bool:
        """Check if an object exists."""
        try:
            self.client.head_object(Bucket=self.config.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def list_keys(self, prefix: str) -> list:
        """List all keys with a given prefix."""
        keys = []
        paginator = self.client.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=self.config.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])

        return keys

    def ensure_bucket(self):
        """Ensure the bucket exists (for testing/setup)."""
        try:
            self.client.head_bucket(Bucket=self.config.bucket)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                self.client.create_bucket(
                    Bucket=self.config.bucket,
                    CreateBucketConfiguration=(
                        {"LocationConstraint": self.config.region}
                        if self.config.region != "us-east-1"
                        else {}
                    ),
                )
                logger.info(f"Created bucket: {self.config.bucket}")


class IntegrityError(Exception):
    """Raised when data integrity check fails."""

    pass


class KeyNotFoundError(Exception):
    """Raised when a key is not found in S3."""

    pass
