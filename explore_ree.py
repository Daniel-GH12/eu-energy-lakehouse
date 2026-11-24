import json
from pathlib import Path

import httpx

TARGET_DATE = "2025-11-01"
URL = (
    "https://apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real"
    f"?start_date={TARGET_DATE}T00:00&end_date={TARGET_DATE}T23:59&time_trunc=hour"
)


def main() -> None:
    response = httpx.get(URL, timeout=30.0)
    response.raise_for_status()

    print("Status code:", response.status_code)
    payload = response.json()
    print("Claves principales del JSON:", list(payload.keys()))

    # 1. Inspección de series en `included`
    print("\n--- Series en 'included' ---")
    for item in payload.get("included", []):
        attributes = item["attributes"]
        title = attributes["title"]
        values = attributes["values"]

        print(f"\nTítulo: {title}")
        print(f"Número de registros: {len(values)}")
        print("Primeros 2 registros:")
        for record in values[:2]:
            print(f"  {record}")

    # 2. Persistencia en capa Bronze (sin transformar el JSON original)
    output_path = (
        Path("data") / "bronze" / "ree_prices" / f"date={TARGET_DATE}" / "raw.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    print(f"\nArchivo Bronze guardado en: {output_path}")


if __name__ == "__main__":
    main()
