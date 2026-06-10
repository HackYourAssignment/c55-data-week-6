"""Week 6 assignment: Azure-deployed data pipeline.

This pipeline replaces the local file output from Week 5 with two cloud
targets: raw JSON in Azure Blob Storage and structured rows in Azure
Database for PostgreSQL. When you finish the assignment it will run as a
Container App Job triggered from the Azure Portal or the CLI.

Replace every `raise NotImplementedError` below with a real implementation.

Reference chapters:
- Blob upload:      Data Track/Week 6/week_6__3_azure_blob_storage.md
- Postgres connect: Data Track/Week 6/week_6__4_azure_postgresql.md
- Container Job:    Data Track/Week 6/week_6__5_container_apps_jobs.md
"""

import logging
import os
from datetime import date

import json
from contextlib import closing

try:
    import psycopg2  # type: ignore[import]
except ImportError as exc:
    raise ImportError(
        """psycopg2 is required to run this pipeline. 
        Install it with `pip install psycopg2-binary`."""
    ) from exc
from azure.storage.blob import BlobServiceClient


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("azure").setLevel(logging.WARNING)

# TASK 3 hint: quiet the Azure SDK so its DEBUG output does not drown your own
# pipeline logs. The right call lives in Chapter 5 (Viewing logs).


def get_config() -> dict:
    """Return configuration read from environment variables.

    Required:
        - POSTGRES_URL: full Azure Postgres connection string.
        - AZURE_STORAGE_CONNECTION_STRING: blob storage account connection string.

    Optional:
        - SOURCE_NAME: logical source label, default "weather".
        - LOG_LEVEL: not parsed here; the orchestrator sets it via env var.

    Raise RuntimeError with a clear message if a required variable is missing.
    """

    postqres_url = os.environ.get("POSTGRES_URL")
    storage_connection = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    source_name = os.environ.get("SOURCE_NAME", "weather")

    missing = []
    if not postqres_url:
        missing.append("POSTGRES_URL")
    if not storage_connection:
        missing.append("AZURE_STORAGE_CONNECTION_STRING")
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    return {
        "postgres_url": postqres_url,
        "azure_storage_connection": storage_connection,
        "source_name": source_name,
    }


def fetch_records() -> list[dict]:
    """Return a small batch of records to ingest.

    In a real pipeline you would call an API here. Return a list of at least
    one dict with a stable key set (for example: station, timestamp,
    temperature_c, humidity_pct).
    """
    return [
        {
            "station": "Eindhoven",
            "timestamp": f"{date.today().isoformat()}T6:00:00Z",
            "temperature_c": 18.5,
            "humidity_pct": 72,
        }
    ]


def upload_raw_to_blob(records: list[dict], blob_conn_str: str, source: str) -> str:
    """Upload the raw records as a single JSON blob and return its name.

    The blob name must follow the assignment convention:
        raw/<source>/<YYYY-MM-DD>.json

    Use the azure-storage-blob SDK. The target container is "raw" (your
    teacher has pre-created it). Overwrite if the blob already exists so
    same-day reruns succeed.
    """
    blob_name = f"raw/{source}/{date.today().isoformat()}.json"
    client = BlobServiceClient.from_connection_string(blob_conn_str)
    container_client = client.get_container_client("raw")

    data = json.dumps(records, indent=2).encode("utf-8")

    container_client.upload_blob(blob_name, data, overwrite=True)

    return blob_name


def write_to_postgres(records: list[dict], postgres_url: str) -> int:
    """Insert (or upsert) records into Azure Postgres. Return the row count.

    Steps:
        1. Open a psycopg2 connection wrapped so it is closed cleanly when the
           function returns, even on error.
        2. Ensure the target table exists (create it if missing).
        3. Insert each record. The pipeline must be safe to rerun on the same
           day: a re-run must update rather than fail.
        4. Commit and return the number of rows written.

    See Chapter 4 for the connection-and-cursor pattern this is based on.
    """
    with closing(psycopg2.connect(postgres_url)) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS weather (
                    station TEXT,
                    timestamp TIMESTAMPTZ,
                    temperature_c REAL,
                    humidity_pct REAL,
                    PRIMARY KEY (station, timestamp)
                )
                """
            )

            for record in records:
                cursor.execute(
                    """
                    INSERT INTO weather (
                    station, timestamp, temperature_c, humidity_pct
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (station, timestamp) DO UPDATE
                    SET temperature_c = EXCLUDED.temperature_c,
                        humidity_pct = EXCLUDED.humidity_pct
                    """,
                    (
                        record["station"],
                        record["timestamp"],
                        record["temperature_c"],
                        record["humidity_pct"],
                    ),
                )

        conn.commit()
        return len(records)


def run() -> None:
    """Run the pipeline end to end."""
    config = get_config()
    logger.info("starting pipeline")
    records = fetch_records()

    blob_name = upload_raw_to_blob(
        records,
        config["azure_storage_connection"],
        config["source_name"],
    )
    logger.info("uploaded blob %s", blob_name)

    row_count = write_to_postgres(records, config["postgres_url"])
    logger.info("wrote %d rows to postgres", row_count)

    logger.info("pipeline complete (today=%s)", date.today().isoformat())


if __name__ == "__main__":
    run()
