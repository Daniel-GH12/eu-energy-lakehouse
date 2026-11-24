"""Tests unitarios para el almacenamiento agnóstico (Local vs. AWS S3)."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_httpx import HTTPXMock

from energy_lakehouse import pipeline, storage

SAMPLE_PAYLOAD = {
    "data": {"id": "mer13"},
    "included": [
        {
            "attributes": {
                "title": "PVPC",
                "values": [
                    {
                        "value": 95.0,
                        "percentage": 0.5,
                        "datetime": "2025-11-01T00:00:00.000+01:00",
                    }
                ],
            }
        },
        {
            "attributes": {
                "title": "Precio mercado spot",
                "values": [
                    {
                        "value": 42.0,
                        "percentage": 0.5,
                        "datetime": "2025-11-01T00:00:00.000+01:00",
                    }
                ],
            }
        },
    ],
}


def test_sync_artifact_local_mode_skips_s3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("S3_BUCKET", raising=False)
    sample_file = tmp_path / "raw.json"
    sample_file.write_text("{}", encoding="utf-8")
    mock_client = MagicMock()

    target = storage.sync_artifact_if_s3_enabled(
        local_path=sample_file,
        s3_key="bronze/ree_prices/date=2025-11-01/raw.json",
        s3_client=mock_client,
    )

    assert target == str(sample_file)
    mock_client.upload_file.assert_not_called()


def test_sync_artifact_uploads_to_s3_when_bucket_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("S3_BUCKET", "eu-energy-lakehouse-test")
    sample_file = tmp_path / "prices.parquet"
    sample_file.write_bytes(b"PAR1")
    mock_client = MagicMock()

    target = storage.sync_artifact_if_s3_enabled(
        local_path=sample_file,
        s3_key="silver/ree_prices/date=2025-11-01/prices.parquet",
        s3_client=mock_client,
    )

    assert target == (
        "s3://eu-energy-lakehouse-test/silver/ree_prices/date=2025-11-01/prices.parquet"
    )
    mock_client.upload_file.assert_called_once_with(
        str(sample_file),
        "eu-energy-lakehouse-test",
        "silver/ree_prices/date=2025-11-01/prices.parquet",
    )


def test_pipeline_uploads_bronze_and_silver_when_s3_bucket_env_set(
    tmp_path: Path,
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("S3_BUCKET", "eu-energy-prod")
    httpx_mock.add_response(json=SAMPLE_PAYLOAD)

    mock_s3 = MagicMock()
    monkeypatch.setattr(storage.boto3, "client", lambda *_a, **_kw: mock_s3)
    monkeypatch.setattr(
        pipeline.subprocess,
        "run",
        lambda cmd, *, check=False: subprocess.CompletedProcess(args=cmd, returncode=0),
    )

    pipeline.run_pipeline(
        target_date=date(2025, 11, 1),
        data_dir=tmp_path / "data",
        dbt_dir=Path("dbt"),
    )

    uploaded_keys = [call.args[2] for call in mock_s3.upload_file.call_args_list]
    assert uploaded_keys == [
        "bronze/ree_prices/date=2025-11-01/raw.json",
        "silver/ree_prices/date=2025-11-01/prices.parquet",
    ]
