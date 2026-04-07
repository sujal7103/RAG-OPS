"""S3-compatible object-store helpers for run artifacts."""

from __future__ import annotations

import logging
from pathlib import Path

from rag_ops.models import BenchmarkArtifacts
from rag_ops.settings import ServiceSettings, get_settings

logger = logging.getLogger(__name__)


class ObjectStoreClient:
    """Upload benchmark artifacts to S3-compatible object storage when enabled."""

    def __init__(self, settings: ServiceSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = None

    @property
    def enabled(self) -> bool:
        return self.settings.object_store_enabled

    def _build_client(self):
        if not self.enabled:
            return None
        if self._client is not None:
            return self._client
        try:
            import boto3
        except ModuleNotFoundError:
            logger.warning("Object store is enabled but boto3 is not installed")
            return None

        session = boto3.session.Session()
        self._client = session.client(
            "s3",
            endpoint_url=self.settings.object_store_endpoint,
            region_name=self.settings.object_store_region,
            aws_access_key_id=self.settings.object_store_access_key or None,
            aws_secret_access_key=self.settings.object_store_secret_key or None,
        )
        return self._client

    def ping(self) -> bool:
        """Return whether the configured object store is reachable."""
        if not self.enabled:
            return False
        client = self._build_client()
        if client is None:
            return False
        try:
            client.head_bucket(Bucket=self.settings.object_store_bucket)
            return True
        except Exception:
            try:
                client.create_bucket(Bucket=self.settings.object_store_bucket)
                return True
            except Exception:
                return False

    def upload_artifact_bundle(self, artifact: BenchmarkArtifacts) -> BenchmarkArtifacts:
        """Upload a completed run's artifact bundle and return object-store URIs."""
        if not self.enabled:
            return artifact
        client = self._build_client()
        if client is None:
            return artifact

        bucket = self.settings.object_store_bucket
        base_prefix = self.settings.object_store_key_prefix.strip("/ ")
        run_prefix = f"{base_prefix}/{artifact.run_id}" if base_prefix else artifact.run_id

        try:
            client.head_bucket(Bucket=bucket)
        except Exception:
            try:
                client.create_bucket(Bucket=bucket)
            except Exception as exc:
                logger.warning("Could not ensure object-store bucket %s: %s", bucket, exc)
                return artifact

        uploaded = {
            "directory": f"s3://{bucket}/{run_prefix}",
        }
        for attribute_name in ("summary_json", "results_csv", "results_json", "per_query_json"):
            local_path = Path(getattr(artifact, attribute_name))
            object_key = f"{run_prefix}/{local_path.name}"
            try:
                client.upload_file(str(local_path), bucket, object_key)
            except Exception as exc:
                logger.warning("Could not upload %s for run %s: %s", local_path, artifact.run_id, exc)
                return artifact
            uploaded[attribute_name] = f"s3://{bucket}/{object_key}"

        return BenchmarkArtifacts(
            run_id=artifact.run_id,
            directory=uploaded["directory"],
            summary_json=uploaded["summary_json"],
            results_csv=uploaded["results_csv"],
            results_json=uploaded["results_json"],
            per_query_json=uploaded["per_query_json"],
        )
