"""Orquestador local unificado del Lakehouse: Bronze -> Silver -> Gold."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

import httpx

from energy_lakehouse.ingestion.ree_client import fetch_ree_prices, save_to_bronze
from energy_lakehouse.transformation.silver_prices import (
    parse_bronze_prices,
    save_to_silver,
)

logger = logging.getLogger(__name__)


def _resolve_dbt_executable() -> str:
    """Localiza el ejecutable de dbt junto al intérprete activo de Python."""
    binary_name = "dbt.exe" if sys.platform == "win32" else "dbt"
    candidate = Path(sys.executable).parent / binary_name
    if candidate.is_file():
        return str(candidate)
    return "dbt"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parsea los argumentos de línea de comandos del pipeline."""
    default_date = date.today() - timedelta(days=1)
    parser = argparse.ArgumentParser(
        description="Ejecuta el pipeline completo REE (Bronze -> Silver -> Gold).",
    )
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=default_date,
        help=(
            "Fecha objetivo en formato YYYY-MM-DD "
            f"(por defecto ayer: {default_date.isoformat()})."
        ),
    )
    return parser.parse_args(argv)


def run_dbt(command: str, dbt_dir: Path = Path("dbt")) -> None:
    """Ejecuta un subcomando de dbt (`run` o `test`) fallando si devuelve error."""
    dbt_bin = _resolve_dbt_executable()
    cmd = [
        dbt_bin,
        command,
        "--project-dir",
        str(dbt_dir),
        "--profiles-dir",
        str(dbt_dir),
    ]
    logger.info("Ejecutando comando dbt: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)


def run_pipeline(
    target_date: date,
    data_dir: Path = Path("data"),
    dbt_dir: Path = Path("dbt"),
) -> None:
    """Ejecuta en orden estricto las fases Bronze, Silver y Gold para una fecha."""
    date_str = target_date.isoformat()
    logger.info("=== Iniciando pipeline para la fecha %s ===", date_str)

    # Fase 1: Ingesta -> Bronze
    logger.info("[Fase 1/3 - Bronze] Inicio de ingesta desde API de REE")
    with httpx.Client(timeout=10.0) as client:
        raw_payload = fetch_ree_prices(target_date, client=client)
    bronze_path = save_to_bronze(
        raw_payload,
        target_date,
        base_dir=data_dir / "bronze",
    )
    logger.info("[Fase 1/3 - Bronze] Completada -> %s", bronze_path)

    # Fase 2: Transformación y contrato Pandera -> Silver
    logger.info("[Fase 2/3 - Silver] Inicio de limpieza y validación")
    silver_df = parse_bronze_prices(raw_payload)
    silver_path = save_to_silver(
        silver_df,
        target_date,
        base_dir=data_dir / "silver",
    )
    logger.info(
        "[Fase 2/3 - Silver] Completada (%d filas) -> %s",
        len(silver_df),
        silver_path,
    )

    # Fase 3: Modelos analíticos y tests dbt -> Gold
    logger.info("[Fase 3/3 - Gold] Inicio de dbt run y dbt test")
    (data_dir / "gold").mkdir(parents=True, exist_ok=True)
    run_dbt("run", dbt_dir=dbt_dir)
    run_dbt("test", dbt_dir=dbt_dir)
    logger.info("[Fase 3/3 - Gold] Completada con éxito")

    logger.info("=== Pipeline finalizado con éxito para %s ===", date_str)


def main(argv: Sequence[str] | None = None) -> None:
    """Punto de entrada CLI del orquestador."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    args = parse_args(argv)
    run_pipeline(args.date)


if __name__ == "__main__":
    main()
