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
from contextlib import closing
import psycopg2
import json

from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("azure").setLevel(logging.WARNING)
# TASK 3 hint: quiet the Azure SDK so its DEBUG output does not drown your own
# pipeline logs. The right call lives in Chapter 5 (Viewing logs).
logging.getLogger("azure.storage.blob").setLevel(logging.WARNING)
logging.getLogger("psycopg2").setLevel(logging.WARNING)


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
    postgres_url = os.getenv("POSTGRES_URL")
    blob_conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    source_name = os.getenv("SOURCE_NAME", "weather")
    schema = os.getenv("PG_SCHEMA", "dev_baraah")

    if not postgres_url:
        raise RuntimeError("Missing required environment variable: POSTGRES_URL")
    
    if not blob_conn:
        raise RuntimeError("Missing required environment variable: AZURE_STORAGE_CONNECTION_STRING")
    
    if not source_name:
        raise RuntimeError("Missing required environment variable: SOURCE_NAME")
    
    return {
        "postgres_url": postgres_url,
        "azure_storage_connection_string": blob_conn,
        "source_name": source_name,
        "schema": schema,
    }

    raise NotImplementedError(
        "Task 3: read POSTGRES_URL and AZURE_STORAGE_CONNECTION_STRING from os.environ"
         
    )


def fetch_records() -> list[dict]:
    """Return a small batch of records to ingest.

    In a real pipeline you would call an API here. Return a list of at least
    one dict with a stable key set (for example: station, timestamp,
    temperature_c, humidity_pct).
    """
    return [
        {
            "station": "AMS",
            "date": date.today().isoformat(),
            "temperature_c": 20.5,
            "humidity_pct": 60,
        },
        {
            "station": "RTM",
            "date": date.today().isoformat(),
            "temperature_c": 18.2,
            "humidity_pct": 70,
        },
    ]
    raise NotImplementedError("Task 3: return a list of at least one record")


def upload_raw_to_blob(records: list[dict], blob_conn_str: str, source: str) -> str:
    """Upload the raw records as a single JSON blob and return its name.

    The blob name must follow the assignment convention:
        raw/<source>/<YYYY-MM-DD>.json

    Use the azure-storage-blob SDK. The target container is "raw" (your
    teacher has pre-created it). Overwrite if the blob already exists so
    same-day reruns succeed.
    """
    logger.info("uploading to blob storage")

    blob_service = BlobServiceClient.from_connection_string(blob_conn_str)

    container_name = "raw"
    blob_name = f"raw/{source}/{date.today().isoformat()}.json"

    blob_client = blob_service.get_blob_client(
        container=container_name,
        blob=blob_name
    )

    data = json.dumps(records, indent=2)

    blob_client.upload_blob(data, overwrite=True)

    return blob_name
    raise NotImplementedError("Task 1 + Task 3: upload records to blob storage")


def write_to_postgres(records: list[dict], postgres_url: str, schema: str) -> int:
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
    logger.info("writing to postgres")

    with closing(psycopg2.connect(postgres_url)) as conn:
        with conn.cursor() as cur:

            # Create schema
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")

            # Use schema (IMPORTANT requirement)
            cur.execute(f"SET search_path TO {schema};")

            # Create table inside schema
            cur.execute("""
                CREATE TABLE IF NOT EXISTS weather_readings (
                    station TEXT,
                    date DATE,
                    temperature_c FLOAT,
                    humidity_pct FLOAT,
                    PRIMARY KEY (station, date)
                );
            """)

            # 4. Insert / upsert
            for r in records:
                cur.execute("""
                    INSERT INTO weather_readings
                    (station, date, temperature_c, humidity_pct)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (station, date)
                    DO UPDATE SET
                        temperature_c = EXCLUDED.temperature_c,
                        humidity_pct = EXCLUDED.humidity_pct;
                """, (
                    r["station"],
                    r["date"],
                    r["temperature_c"],
                    r["humidity_pct"]
                ))

            conn.commit()

    return len(records)

    raise NotImplementedError("Task 2 + Task 3: insert rows into Azure Postgres")


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

    row_count = write_to_postgres(records, config["postgres_url"], config["schema"])
    logger.info("wrote %d rows to postgres", row_count)

    logger.info("pipeline complete (today=%s)", date.today().isoformat())


if __name__ == "__main__":
    run()
