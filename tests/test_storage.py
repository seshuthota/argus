"""Tests for remote artifact storage backends and report persistence hooks."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from argus.config import load_gcs_storage_config, load_s3_storage_config
from argus.orchestrator.runner import RunArtifact
from argus.reporting.scorecard import save_run_report
from argus.reporting.suite import save_suite_report
from argus.scoring.engine import ScoreCard
from argus.storage.factory import create_storage
from argus.storage.gcs_storage import GCSStorage
from argus.storage.s3_storage import S3Storage


class _FakeBlob:
    def __init__(self, key: str) -> None:
        self.key = key
        self.upload_calls: list[tuple[bytes, str | None]] = []

    def upload_from_string(self, data: bytes, content_type: str | None = None) -> None:
        self.upload_calls.append((data, content_type))


class _FakeBucket:
    def __init__(self) -> None:
        self.blobs: dict[str, _FakeBlob] = {}

    def blob(self, key: str) -> _FakeBlob:
        blob = _FakeBlob(key)
        self.blobs[key] = blob
        return blob


class _FakeGCSClient:
    def __init__(self) -> None:
        self.buckets: dict[str, _FakeBucket] = {}

    def bucket(self, name: str) -> _FakeBucket:
        bucket = self.buckets.get(name)
        if bucket is None:
            bucket = _FakeBucket()
            self.buckets[name] = bucket
        return bucket


def _scorecard(run_id: str = "run_1") -> ScoreCard:
    return ScoreCard(
        run_id=run_id,
        scenario_id="SCENARIO_001",
        model="MiniMax-M2.1",
        task_success=5,
        harm_or_risk=0,
        constraint_violations=0,
        permission_discipline=5,
        tool_hygiene=5,
        total_severity=0,
        checks=[],
        passed=True,
        grade="A",
    )


def _artifact(run_id: str = "run_1") -> RunArtifact:
    return RunArtifact(
        run_id=run_id,
        scenario_id="SCENARIO_001",
        scenario_version="1.0.0",
        model="MiniMax-M2.1",
        settings={"temperature": 0.0},
        start_time=0.0,
        end_time=1.5,
    )


class StorageConfigTests(unittest.TestCase):
    def test_storage_config_loaders_read_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AWS_ACCESS_KEY_ID": "aws-key",
                "AWS_SECRET_ACCESS_KEY": "aws-secret",
                "S3_BUCKET": "argus-s3",
                "GCS_PROJECT": "argus-project",
                "GCS_BUCKET": "argus-gcs",
                "GCS_CREDS_PATH": "/tmp/gcs-creds.json",
            },
            clear=True,
        ):
            s3_cfg = load_s3_storage_config()
            gcs_cfg = load_gcs_storage_config()

        self.assertEqual(s3_cfg.aws_access_key_id, "aws-key")
        self.assertEqual(s3_cfg.aws_secret_access_key, "aws-secret")
        self.assertEqual(s3_cfg.bucket, "argus-s3")
        self.assertEqual(gcs_cfg.project, "argus-project")
        self.assertEqual(gcs_cfg.bucket, "argus-gcs")
        self.assertEqual(gcs_cfg.creds_path, "/tmp/gcs-creds.json")


class StorageBackendTests(unittest.TestCase):
    def test_s3_storage_save_text_uses_put_object(self) -> None:
        client = MagicMock()
        storage = S3Storage(bucket="bucket-a", prefix="reports/runs", client=client)

        uri = storage.save_text(
            text='{"hello":"world"}',
            relative_path="run_1.json",
            content_type="application/json",
        )

        self.assertEqual(uri, "s3://bucket-a/reports/runs/run_1.json")
        client.put_object.assert_called_once_with(
            Bucket="bucket-a",
            Key="reports/runs/run_1.json",
            Body=b'{"hello":"world"}',
            ContentType="application/json",
        )

    def test_gcs_storage_save_text_uploads_blob(self) -> None:
        client = _FakeGCSClient()
        storage = GCSStorage(bucket="bucket-b", prefix="reports/suites", client=client)

        uri = storage.save_text(
            text='{"suite":"ok"}',
            relative_path="suite_1.json",
            content_type="application/json",
        )

        self.assertEqual(uri, "gs://bucket-b/reports/suites/suite_1.json")
        blob = client.buckets["bucket-b"].blobs["reports/suites/suite_1.json"]
        self.assertEqual(blob.upload_calls, [(b'{"suite":"ok"}', "application/json")])


class StorageFactoryTests(unittest.TestCase):
    def test_factory_creates_s3_from_uri(self) -> None:
        with patch("argus.storage.factory.S3Storage") as mock_storage:
            marker = object()
            mock_storage.return_value = marker
            created = create_storage("s3://my-s3/reports/runs")

        self.assertIs(created, marker)
        mock_storage.assert_called_once()
        kwargs = mock_storage.call_args.kwargs
        self.assertEqual(kwargs["bucket"], "my-s3")
        self.assertEqual(kwargs["prefix"], "reports/runs")

    def test_factory_creates_gcs_from_uri(self) -> None:
        with patch("argus.storage.factory.GCSStorage") as mock_storage:
            marker = object()
            mock_storage.return_value = marker
            created = create_storage("gs://my-gcs/reports/suites")

        self.assertIs(created, marker)
        mock_storage.assert_called_once()
        kwargs = mock_storage.call_args.kwargs
        self.assertEqual(kwargs["bucket"], "my-gcs")
        self.assertEqual(kwargs["prefix"], "reports/suites")

    def test_factory_uses_env_bucket_when_uri_bucket_missing(self) -> None:
        with patch.dict(os.environ, {"S3_BUCKET": "env-s3-bucket"}, clear=True), patch(
            "argus.storage.factory.S3Storage"
        ) as mock_storage:
            marker = object()
            mock_storage.return_value = marker
            created = create_storage("s3:///reports/runs")

        self.assertIs(created, marker)
        self.assertEqual(mock_storage.call_args.kwargs["bucket"], "env-s3-bucket")
        self.assertEqual(mock_storage.call_args.kwargs["prefix"], "reports/runs")

    def test_factory_requires_bucket_for_s3(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                create_storage("s3:///reports/runs")


class ReportingStorageIntegrationTests(unittest.TestCase):
    def test_save_run_report_remote_uses_storage_factory(self) -> None:
        storage = MagicMock()
        storage.save_text.return_value = "s3://argus-bucket/reports/runs/run_1.json"
        with patch("argus.reporting.scorecard.create_storage", return_value=storage) as mock_factory:
            report_ref = save_run_report(
                _scorecard(),
                _artifact(),
                output_uri="s3://argus-bucket/reports/runs",
            )

        self.assertEqual(report_ref, "s3://argus-bucket/reports/runs/run_1.json")
        mock_factory.assert_called_once_with("s3://argus-bucket/reports/runs")
        storage.save_text.assert_called_once()
        kwargs = storage.save_text.call_args.kwargs
        self.assertEqual(kwargs["relative_path"], "run_1.json")
        self.assertEqual(kwargs["content_type"], "application/json")
        payload = json.loads(kwargs["text"])
        self.assertEqual(payload["run"]["run_id"], "run_1")

    def test_save_suite_report_remote_uses_storage_factory(self) -> None:
        suite_report = {
            "suite_id": "suite_1",
            "summary": {"pass_rate": 1.0},
            "runs": [],
        }
        storage = MagicMock()
        storage.save_text.return_value = "gs://argus-bucket/reports/suites/suite_1.json"
        with patch("argus.reporting.suite.create_storage", return_value=storage) as mock_factory:
            report_ref = save_suite_report(
                suite_report,
                output_uri="gs://argus-bucket/reports/suites",
            )

        self.assertEqual(report_ref, "gs://argus-bucket/reports/suites/suite_1.json")
        mock_factory.assert_called_once_with("gs://argus-bucket/reports/suites")
        kwargs = storage.save_text.call_args.kwargs
        self.assertEqual(kwargs["relative_path"], "suite_1.json")
        self.assertEqual(kwargs["content_type"], "application/json")
        payload = json.loads(kwargs["text"])
        self.assertEqual(payload["suite_id"], "suite_1")

    def test_save_run_report_local_still_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            report_path = save_run_report(_scorecard(), _artifact(), output_dir=td)
            self.assertIsInstance(report_path, Path)
            self.assertTrue(report_path.exists())
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["run"]["run_id"], "run_1")


if __name__ == "__main__":
    unittest.main()

