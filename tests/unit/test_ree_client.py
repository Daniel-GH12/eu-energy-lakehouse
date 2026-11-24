"""Tests unitarios para el cliente de ingesta de REE."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from energy_lakehouse.ingestion.ree_client import fetch_ree_prices, save_to_bronze


def test_save_to_bronze_creates_partitioned_file(tmp_path: Path) -> None:
    target_date = date(2025, 11, 1)
    payload = {
        "data": {"id": "mer13", "type": "Precios mercado peninsular"},
        "included": [{"type": "PVPC", "attributes": {"values": []}}],
    }

    saved_path = save_to_bronze(payload, target_date, base_dir=tmp_path)

    expected_path = tmp_path / "ree_prices" / "date=2025-11-01" / "raw.json"
    assert saved_path == expected_path
    assert expected_path.is_file()

    stored_payload = json.loads(expected_path.read_text(encoding="utf-8"))
    assert stored_payload == payload


def test_fetch_ree_prices_success(httpx_mock: HTTPXMock) -> None:
    expected_payload = {"data": {}, "included": []}
    httpx_mock.add_response(json=expected_payload)

    result = fetch_ree_prices(date(2025, 11, 1))

    assert result == expected_payload
    assert len(httpx_mock.get_requests()) == 1


def test_fetch_ree_prices_does_not_retry_on_404(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(status_code=404)

    with pytest.raises(httpx.HTTPStatusError):
        fetch_ree_prices(date(2025, 11, 1))

    assert len(httpx_mock.get_requests()) == 1
