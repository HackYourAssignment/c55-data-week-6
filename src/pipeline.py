"""Week 6 assignment: Azure-deployed data pipeline.

This pipeline replaces the local file output from Week 5 with two cloud
targets: raw JSON in Azure Blob Storage and structured rows in Azure
Database for PostgreSQL. When you finish the assignment it will run as a
Container App Job triggered from the Azure Portal or the CLI.


Reference chapters:
- Blob upload:      Data Track/Week 6/week_6__3_azure_blob_storage.md
- Postgres connect: Data Track/Week 6/week_6__4_azure_postgresql.md
- Container Job:    Data Track/Week 6/week_6__5_container_apps_jobs.md
"""

import logging
import os
from datetime import date
import sys
import json
from contextlib import closing
import psycopg2
from azure.storage.blob import BlobServiceClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# TASK 3 hint: quiet the Azure SDK so its DEBUG output does not drown your own
# pipeline logs. The right call lives in Chapter 5 (Viewing logs).
logging.getLogger("azure").setLevel(logging.WARNING)

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
    conn_postgres=os.environ.get("POSTGRES_URL")
    if not conn_postgres:
        logging.info(
            "POSTGRES_URL is not set.\n"
            "Retrieve it from Key Vault using the CLI, then export it before running:\n\n"
            "    export POSTGRES_URL=\"$(az keyvault secret show --vault-name kv-hyf-data --name postgres-url --query value -o tsv)\"\n",
            file=sys.stderr,
        )
        raise RuntimeError("missing POSTGRES_URL")
    conn=os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn:
        logging.info(
            "AZURE_STORAGE_CONNECTION_STRING is not set.\n"
            "Retrieve it from Key Vault using the CLI, then export it before running:\n\n"
            "    export AZURE_STORAGE_CONNECTION_STRING=\"$(az keyvault secret show --vault-name kv-hyf-data --name storage-connection-string --query value -o tsv)\"\n",
            file=sys.stderr,
        )
        raise RuntimeError("missing AZURE_STORAGE_CONNECTION_STRING")
    return {
        "postgres_url": conn_postgres,
        "azure_storage_connection_string": conn,
        "source_name": os.environ.get("SOURCE_NAME", "weather"),
    }


def fetch_records() -> list[dict]:
    """Return a small batch of records to ingest.

    In a real pipeline you would call an API here. Return a list of at least
    one dict with a stable key set (for example: station, timestamp,
    temperature_c, humidity_pct).
    """
    mock_record = {
        "station": "Amsterdam",
        "timestamp": "2024-06-01T12:00:00Z",
        "temperature_c": 20.5,
        "humidity_pct": 60,
    }
    return [mock_record]


def upload_raw_to_blob(records: list[dict], blob_conn_str: str, source: str) -> str:
    """Upload the raw records as a single JSON blob and return its name.

    The blob name must follow the assignment convention:
        raw/<source>/<YYYY-MM-DD>.json

    Use the azure-storage-blob SDK. The target container is "raw" (your
    teacher has pre-created it). Overwrite if the blob already exists so
    same-day reruns succeed.
    """
    blob_service_client = BlobServiceClient.from_connection_string(blob_conn_str)
    container_client = blob_service_client.get_container_client("raw")
    blob_name = f"raw/{source}/{date.today().isoformat()}.json"
    json_data = json.dumps(records)
    container_client.upload_blob(blob_name, data=json_data, overwrite=True)
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
    # its already added sslmode=require to the connection string, so we can just use it as is
    with closing(psycopg2.connect(postgres_url)) as conn:
        # with psycopg2.connect(postgres_url)as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS dev_mareh;")
            cur.execute("SET search_path TO dev_mareh;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS weather_readings (
                    station VARCHAR(50),
                    timestamp TIMESTAMPTZ,
                    temperature_c FLOAT,
                    humidity_pct INT,
                    PRIMARY KEY (station, timestamp)
                );
            """)
            for each_record in records:
                cur.execute(
                    """
                    INSERT INTO weather_readings (station, timestamp, temperature_c, humidity_pct)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (station, timestamp) DO UPDATE
                    SET temperature_c = EXCLUDED.temperature_c,
                        humidity_pct = EXCLUDED.humidity_pct;
                """,
                    (
                        each_record["station"],
                        each_record["timestamp"],
                        each_record["temperature_c"],
                        each_record["humidity_pct"],
                    ),
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
