"""Abstracción de almacenamiento agnóstica al entorno (Local vs. AWS S3)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import boto3

logger = logging.getLogger(__name__)


def get_s3_bucket() -> str | None:
    """Devuelve el nombre del bucket S3 configurado en `S3_BUCKET`, o `None`."""
    bucket = os.getenv("S3_BUCKET", "").strip()
    return bucket or None


def upload_file_to_s3(
    local_path: Path,
    bucket: str,
    key: str,
    s3_client: Any | None = None,
) -> str:
    """Sube un archivo local a `s3://<bucket>/<key>` y devuelve su URI S3."""
    client = s3_client or boto3.client(
        "s3",
        region_name=os.getenv("AWS_REGION", "eu-west-1"),
    )
    client.upload_file(str(local_path), bucket, key)
    uri = f"s3://{bucket}/{key}"
    logger.info("Artefacto subido a S3: %s", uri)
    return uri


def sync_artifact_if_s3_enabled(
    local_path: Path,
    s3_key: str,
    s3_bucket: str | None = None,
    s3_client: Any | None = None,
) -> str:
    """Sube el artefacto a S3 si hay bucket configurado; si no, mantiene modo local.

    Args:
        local_path: Ruta local del archivo recién generado.
        s3_key: Clave destino dentro del bucket S3 (sin barra inicial).
        s3_bucket: Nombre de bucket explícito; si es `None`, lee `S3_BUCKET`.
        s3_client: Cliente boto3 opcional (útil para inyección en tests).

    Returns:
        URI `s3://...` si se subió a S3, o la ruta local en formato string.
    """
    bucket = s3_bucket if s3_bucket is not None else get_s3_bucket()
    if not bucket:
        logger.debug("S3_BUCKET no definida; modo local activo (%s)", local_path)
        return str(local_path)

    return upload_file_to_s3(
        local_path=local_path,
        bucket=bucket,
        key=s3_key,
        s3_client=s3_client,
    )
