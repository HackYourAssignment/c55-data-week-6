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

import json
import logging
import os
from datetime import date
import sys
from zipfile import Path
import psycopg2
from azure.storage.blob import BlobServiceClient
from contextlib import closing


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("azure").setLevel(logging.WARNING)

CREATE_WEATHER_READINGS_SQL = """
CREATE TABLE IF NOT EXISTS weather_readings (
    id SERIAL PRIMARY KEY,
    station TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    temperature_c DOUBLE PRECISION NOT NULL
)
"""

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
    POSTGRES_URL = os.environ.get("POSTGRES_URL")
    AZURE_STORAGE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    SOURCE_NAME = os.environ.get("SOURCE_NAME", "weather")

    missing = []
    if not POSTGRES_URL:
        missing.append("POSTGRES_URL")
    if not AZURE_STORAGE_CONNECTION_STRING:
        missing.append("AZURE_STORAGE_CONNECTION_STRING")
    if not SOURCE_NAME:
        missing.append("SOURCE_NAME")
    if missing:
        print(
            f"Error: missing environment variable(s): {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)
    return {
        "postgres_url": POSTGRES_URL,
        "azure_storage_connection_string": AZURE_STORAGE_CONNECTION_STRING,
        "source_name": SOURCE_NAME,
    }


def fetch_records() -> list[dict]:
    """Return a small batch of records to ingest.

    In a real pipeline you would call an API here. Return a list of at least
    one dict with a stable key set (for example: station, timestamp,
    temperature_c, humidity_pct).
    """
    return [
        {
            "station": "STATION_1",
            "timestamp": "2024-06-01T12:00:00Z",
            "temperature_c": 25.0,
            "humidity_pct": 60.0,
        },
        {
            "station": "STATION_2",
            "timestamp": "2024-06-01T12:05:00Z",
            "temperature_c": 26.5,
            "humidity_pct": 55.0,
        },
    ]


def upload_raw_to_blob(records: list[dict], blob_conn_str: str, source: str) -> str:
    """Upload the raw records as a single JSON blob and return its name.

    The blob name must follow the assignment convention:
        raw/<source>/<YYYY-MM-DD>.json

    Use the azure-storage-blob SDK. The target container is "raw" (your
    teacher has pre-created it). Overwrite if the blob already exists so
    same-day reruns succeed.
    """
    service = BlobServiceClient.from_connection_string(blob_conn_str)
    container = service.get_container_client("raw")
    data = json.dumps(records)
    blob_name = f"{source}/{date.today().isoformat()}.json"
    container.upload_blob(name=blob_name, data=data, overwrite=True)
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
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS dev_bader;")
            cur.execute("SET search_path TO dev_bader;")
            cur.execute(CREATE_WEATHER_READINGS_SQL)
            for row in records:
                cur.execute(
                    """
                        INSERT INTO weather_readings (station, timestamp, temperature_c)
                        VALUES (%s, %s, %s)
                        """,
                    (row["station"], row["timestamp"], float(row["temperature_c"])),
                )
                conn.commit()
            return len(records)


def run() -> None:
    config = get_config()
    logger.info("starting pipeline")
    records = fetch_records()

    blob_name = upload_raw_to_blob(
        records,
        config["azure_storage_connection_string"],
        config["source_name"],
    )
    logger.info("uploaded blob %s", blob_name)

    row_count = write_to_postgres(records, config["postgres_url"])
    logger.info("wrote %d rows to postgres", row_count)

    logger.info("pipeline complete (today=%s)", date.today().isoformat())


if __name__ == "__main__":
    run()
