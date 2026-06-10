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
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError
import psycopg2
from contextlib import closing
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# TASK 3 hint: quiet the Azure SDK so its DEBUG output does not drown your own
# pipeline logs. The right call lives in Chapter 5 (Viewing logs).
logging.getLogger("azure").setLevel(logging.WARNING)

load_dotenv()


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
    source_name = os.getenv("SOURCE_NAME", "weather")
    POSTGRES_URL = os.getenv("POSTGRES_URL")
    AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

    if not POSTGRES_URL:
        raise RuntimeError("Environment variable 'POSTGRES_URL' is not set")
    if not AZURE_STORAGE_CONNECTION_STRING:
        raise RuntimeError("Environment variable 'AZURE_STORAGE_CONNECTION_STRING' is not set")

    return {
        "source_name": source_name,
        "postgres_url": POSTGRES_URL,
        "azure_storage_connection_string": AZURE_STORAGE_CONNECTION_STRING,
    }


def fetch_records() -> list[dict]:
    """Return a small batch of records to ingest.

    In a real pipeline you would call an API here. Return a list of at least
    one dict with a stable key set (for example: station, timestamp,
    temperature_c, humidity_pct).
    """
    logger.info("fetching records from source API") 

    return [
        {
            "station": "Amsterdam",
            "timestamp": "2026-06-09T06:00:00Z",
            "temperature_c": 17.4,
            "humidity_pct": 72,
        },
        {
            "station": "Rotterdam",
            "timestamp": "2026-06-09T06:00:00Z",
            "temperature_c": 16.8,
            "humidity_pct": 68,
        },
        {
            "station": "Almere",
            "timestamp": "2026-06-09T06:00:00Z",
            "temperature_c": 15.9,
            "humidity_pct": 75,
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
    logger.info("connecting to blob service")
    blob_service_client = BlobServiceClient.from_connection_string(blob_conn_str)

    container_name = "raw"
    blob_path = f"{source}/{date.today().isoformat()}.json"

    # Ensure the container exists so uploads don't fail with PathNotFoundError.
    try:
        logger.info("ensuring container '%s' exists", container_name)
        blob_service_client.create_container(container_name)
    except ResourceExistsError:
        pass
    except Exception:
        logger.exception("failed to create or access container '%s'", container_name)
        raise

    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_path)

    # Always upload and overwrite same-day blobs so reruns succeed.
    logger.info("uploading blob %s (overwrite=true)", blob_path)
    blob_client.upload_blob(data=json.dumps(records), overwrite=True)
    return blob_path


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
            cur.execute("DROP TABLE IF EXISTS weather_readings")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS weather_readings (
                    station TEXT NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL,
                    temperature_c REAL NOT NULL,
                    humidity_pct INTEGER NOT NULL,
                    PRIMARY KEY (station, timestamp)
                )
                """
            )

            insert_sql = """
                INSERT INTO weather_readings (
                    station,
                    timestamp,
                    temperature_c,
                    humidity_pct
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (station, timestamp) DO UPDATE SET
                    temperature_c = EXCLUDED.temperature_c,
                    humidity_pct = EXCLUDED.humidity_pct
            """

            for record in records:
                cur.execute(
                    insert_sql,
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
