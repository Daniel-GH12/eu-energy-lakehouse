"""Transformación y validación de precios REE de capa Bronze a capa Silver."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pandera.pandas as pa

logger = logging.getLogger(__name__)

MARKET_TYPE_MAPPING: dict[str, str] = {
    "PVPC": "pvpc",
    "Precio mercado spot": "spot",
}

SILVER_PRICES_SCHEMA = pa.DataFrameSchema(
    columns={
        "timestamp_utc": pa.Column(
            pd.DatetimeTZDtype(tz="UTC"),
            nullable=False,
        ),
        "market_type": pa.Column(
            str,
            nullable=False,
            checks=pa.Check.isin(["pvpc", "spot"]),
        ),
        "price_eur_mwh": pa.Column(
            float,
            nullable=False,
            checks=[pa.Check.ge(-500.0), pa.Check.le(4000.0)],
        ),
    },
    unique=["timestamp_utc", "market_type"],
    strict=True,
)


def parse_bronze_prices(raw_payload: dict[str, Any]) -> pd.DataFrame:
    """Transforma un payload JSON crudo de REE en un DataFrame limpio para Silver.

    Extrae las series conocidas (`PVPC` -> `pvpc`, `Precio mercado spot` -> `spot`),
    descarta campos auxiliares como `percentage`, normaliza los timestamps a UTC,
    ordena y deduplica por clave de negocio (`timestamp_utc`, `market_type`).

    Args:
        raw_payload: Diccionario JSON tal como fue almacenado en la capa Bronze.

    Returns:
        DataFrame con las columnas `timestamp_utc`, `market_type` y `price_eur_mwh`.
    """
    records: list[dict[str, Any]] = []

    for item in raw_payload.get("included", []):
        attributes = item.get("attributes", {})
        title = attributes.get("title")
        market_type = MARKET_TYPE_MAPPING.get(title)

        if market_type is None:
            logger.warning(
                "Serie desconocida en payload Bronze, se ignora: %r", title
            )
            continue

        for entry in attributes.get("values", []):
            records.append(
                {
                    "timestamp_utc": entry.get("datetime"),
                    "market_type": market_type,
                    "price_eur_mwh": entry.get("value"),
                }
            )

    if not records:
        return pd.DataFrame(
            {
                "timestamp_utc": pd.Series(dtype=pd.DatetimeTZDtype(tz="UTC")),
                "market_type": pd.Series(dtype="object"),
                "price_eur_mwh": pd.Series(dtype="float64"),
            }
        )

    df = pd.DataFrame(records)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True).astype(
        pd.DatetimeTZDtype(tz="UTC")
    )
    df["price_eur_mwh"] = df["price_eur_mwh"].astype(float)

    df = (
        df.sort_values(["market_type", "timestamp_utc"])
        .drop_duplicates(subset=["timestamp_utc", "market_type"], keep="last")
        .reset_index(drop=True)
    )
    return df


def save_to_silver(
    df: pd.DataFrame,
    target_date: date,
    base_dir: Path = Path("data/silver"),
) -> Path:
    """Valida el DataFrame contra el contrato Silver y lo persiste en Parquet.

    Args:
        df: DataFrame transformado listo para validar.
        target_date: Fecha de la partición destino.
        base_dir: Directorio raíz de la capa Silver.

    Returns:
        Ruta del archivo Parquet guardado en disco.

    Raises:
        pandera.errors.SchemaError: Si el DataFrame incumple el contrato Silver.
    """
    validated_df = SILVER_PRICES_SCHEMA.validate(df)

    output_path = (
        base_dir
        / "ree_prices"
        / f"date={target_date.isoformat()}"
        / "prices.parquet"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    validated_df.to_parquet(output_path, index=False)

    logger.info(
        "Capa Silver guardada para %s (%d filas): %s",
        target_date.isoformat(),
        len(validated_df),
        output_path,
    )
    return output_path


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    for day in (date(2025, 11, 1), date(2025, 11, 2)):
        bronze_path = (
            Path("data/bronze") / "ree_prices" / f"date={day.isoformat()}" / "raw.json"
        )
        if not bronze_path.is_file():
            logger.warning("No existe archivo Bronze para %s: %s", day, bronze_path)
            continue

        payload = json.loads(bronze_path.read_text(encoding="utf-8"))
        silver_df = parse_bronze_prices(payload)
        save_to_silver(silver_df, day)
