"""Tests unitarios para el orquestador unificado del pipeline."""

from __future__ import annotations

import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from energy_lakehouse import pipeline

SAMPLE_REE_PAYLOAD = {
    "data": {"id": "mer13"},
    "included": [
        {
            "attributes": {
                "title": "PVPC",
                "values": [
                    {
                        "value": 100.0,
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
                        "value": 45.0,
                        "percentage": 0.5,
                        "datetime": "2025-11-01T00:00:00.000+01:00",
                    }
                ],
            }
        },
    ],
}


def test_parse_args_defaults_to_yesterday() -> None:
    args = pipeline.parse_args([])
    assert args.date == date.today() - timedelta(days=1)


def test_parse_args_accepts_explicit_date() -> None:
    args = pipeline.parse_args(["--date", "2025-11-01"])
    assert args.date == date(2025, 11, 1)


def test_run_pipeline_executes_bronze_silver_gold_in_order(
    tmp_path: Path,
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    httpx_mock.add_response(json=SAMPLE_REE_PAYLOAD)
    dbt_calls: list[list[str]] = []

    def fake_subprocess_run(
        cmd: list[str],
        *,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        dbt_calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_subprocess_run)

    pipeline.run_pipeline(
        target_date=date(2025, 11, 1),
        data_dir=tmp_path / "data",
        dbt_dir=Path("dbt"),
    )

    assert (
        tmp_path / "data" / "bronze" / "ree_prices" / "date=2025-11-01" / "raw.json"
    ).is_file()
    assert (
        tmp_path
        / "data"
        / "silver"
        / "ree_prices"
        / "date=2025-11-01"
        / "prices.parquet"
    ).is_file()
    assert (tmp_path / "data" / "gold").is_dir()

    assert len(dbt_calls) == 2
    assert dbt_calls[0][1:] == ["run", "--project-dir", "dbt", "--profiles-dir", "dbt"]
    assert dbt_calls[1][1:] == ["test", "--project-dir", "dbt", "--profiles-dir", "dbt"]


def test_run_pipeline_propagates_dbt_failure(
    tmp_path: Path,
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    httpx_mock.add_response(json=SAMPLE_REE_PAYLOAD)

    def failing_subprocess_run(
        cmd: list[str],
        *,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

    monkeypatch.setattr(pipeline.subprocess, "run", failing_subprocess_run)

    with pytest.raises(subprocess.CalledProcessError):
        pipeline.run_pipeline(
            target_date=date(2025, 11, 1),
            data_dir=tmp_path / "data",
            dbt_dir=Path("dbt"),
        )
