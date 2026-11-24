"""Tests unitarios para la transformación y contrato de datos Silver."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
import pytest

from energy_lakehouse.transformation.silver_prices import (
    parse_bronze_prices,
    save_to_silver,
)


def test_parse_and_save_silver_valid(tmp_path: Path) -> None:
    target_date = date(2025, 11, 1)
    raw_payload = {
        "data": {"id": "mer13"},
        "included": [
            {
                "attributes": {
                    "title": "PVPC",
                    "values": [
                        {
                            "value": 108.54,
                            "percentage": 0.68,
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
                            "value": -12.5,
                            "percentage": 0.32,
                            "datetime": "2025-11-01T00:15:00.000+01:00",
                        }
                    ],
                }
            },
        ],
    }

    parsed_df = parse_bronze_prices(raw_payload)
    saved_path = save_to_silver(parsed_df, target_date, base_dir=tmp_path)

    expected_path = tmp_path / "ree_prices" / "date=2025-11-01" / "prices.parquet"
    assert saved_path == expected_path
    assert expected_path.is_file()

    loaded_df = pd.read_parquet(expected_path)
    assert list(loaded_df.columns) == [
        "timestamp_utc",
        "market_type",
        "price_eur_mwh",
    ]
    assert loaded_df["timestamp_utc"].dtype == pd.DatetimeTZDtype(tz="UTC")
    assert pd.api.types.is_string_dtype(loaded_df["market_type"])
    assert pd.api.types.is_float_dtype(loaded_df["price_eur_mwh"])

    assert len(loaded_df) == 2
    pvpc_row = loaded_df.loc[loaded_df["market_type"] == "pvpc"].iloc[0]
    spot_row = loaded_df.loc[loaded_df["market_type"] == "spot"].iloc[0]

    # 2025-11-01T00:00+01:00 -> 2025-10-31T23:00:00+00:00
    assert pvpc_row["timestamp_utc"] == pd.Timestamp("2025-10-31T23:00:00Z")
    assert pvpc_row["price_eur_mwh"] == pytest.approx(108.54)

    # 2025-11-01T00:15+01:00 -> 2025-10-31T23:15:00+00:00 (precio negativo válido)
    assert spot_row["timestamp_utc"] == pd.Timestamp("2025-10-31T23:15:00Z")
    assert spot_row["price_eur_mwh"] == pytest.approx(-12.5)


def test_silver_schema_rejects_invalid_market_type(tmp_path: Path) -> None:
    invalid_df = pd.DataFrame(
        {
            "timestamp_utc": pd.to_datetime(
                ["2025-11-01T00:00:00Z"], utc=True
            ).astype(pd.DatetimeTZDtype(tz="UTC")),
            "market_type": ["mercado_inventado"],
            "price_eur_mwh": [50.0],
        }
    )

    with pytest.raises(pa.errors.SchemaError):
        save_to_silver(invalid_df, date(2025, 11, 1), base_dir=tmp_path)

    expected_path = tmp_path / "ree_prices" / "date=2025-11-01" / "prices.parquet"
    assert not expected_path.exists()


def test_silver_schema_rejects_null_price(tmp_path: Path) -> None:
    invalid_df = pd.DataFrame(
        {
            "timestamp_utc": pd.to_datetime(
                ["2025-11-01T00:00:00Z"], utc=True
            ).astype(pd.DatetimeTZDtype(tz="UTC")),
            "market_type": ["pvpc"],
            "price_eur_mwh": [None],
        }
    )

    with pytest.raises(pa.errors.SchemaError):
        save_to_silver(invalid_df, date(2025, 11, 1), base_dir=tmp_path)
