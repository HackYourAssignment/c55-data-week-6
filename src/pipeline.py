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
from contextlib import closing
from datetime import date, datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg2
from azure.storage.blob import BlobServiceClient
from psycopg2.extras import execute_values


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(levelname)s %(message)s",
)

# Required by the assignment: silence noisy Azure SDK logs.
logging.getLogger("azure").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

SCHEMA_NAME = "dev_mohammedalfakih"
TABLE_NAME = "weather_readings"
# TASK 3 hint: quiet the Azure SDK so its DEBUG output does not drown your own
# pipeline logs. The right call lives in Chapter 5 (Viewing logs).

def ensure_sslmode_require(postgres_url: str) -> str:
    """Ensure Azure Postgres connection string uses sslmode=require."""
    parts = urlsplit(postgres_url)
    query = dict(parse_qsl(parts.query))

    if "sslmode" not in query:
        query["sslmode"] = "require"

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def get_config() -> dict:
    """Return configuration read from environment variables.

    Required:
        POSTGRES_URL
        AZURE_STORAGE_CONNECTION_STRING

    Optional:
        SOURCE_NAME, default "weather"
    """
    postgres_url = os.getenv("POSTGRES_URL")
    blob_conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

    missing = []
    if not postgres_url:
        missing.append("POSTGRES_URL")
    if not blob_conn_str:
        missing.append("AZURE_STORAGE_CONNECTION_STRING")

    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return {
        "postgres_url": ensure_sslmode_require(postgres_url),
        "azure_storage_connection_string": blob_conn_str,
        "source_name": os.getenv("SOURCE_NAME", "weather"),
    }


def fetch_records() -> list[dict]:
    """Return a small batch of weather records to ingest."""
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    return [
        {
            "station": "Open-Meteo Copenhagen",
            "timestamp": now,
            "temperature_c": 12.5,
            "humidity_pct": 80,
        },
        {
            "station": "Open-Meteo Amsterdam",
            "timestamp": now,
            "temperature_c": 10.8,
            "humidity_pct": 75,
        },
    ]


def upload_raw_to_blob(records: list[dict], blob_conn_str: str, source: str) -> str:
    """Upload raw records as JSON to Azure Blob Storage."""
    blob_name = f"raw/{source}/{date.today().isoformat()}.json"

    service = BlobServiceClient.from_connection_string(blob_conn_str)
    blob_client = service.get_blob_client(
        container="raw",
        blob=blob_name,
    )

    payload = json.dumps(records, indent=2)

    blob_client.upload_blob(
        payload,
        overwrite=True,
        content_type="application/json",
    )

    return blob_name



def write_to_postgres(records: list[dict], postgres_url: str) -> int:
    """Upsert weather readings into Azure Postgres and return row count."""
    with closing(psycopg2.connect(postgres_url)) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}")
                cur.execute(f"SET search_path TO {SCHEMA_NAME}")

                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                        station TEXT NOT NULL,
                        timestamp TIMESTAMPTZ NOT NULL,
                        temperature_c DOUBLE PRECISION NOT NULL,
                        humidity_pct INTEGER NOT NULL,
                        ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (station, timestamp)
                    )
                    """
                )

                rows = [
                    (
                        record["station"],
                        record["timestamp"],
                        record["temperature_c"],
                        record["humidity_pct"],
                    )
                    for record in records
                ]

                execute_values(
                    cur,
                    f"""
                    INSERT INTO {TABLE_NAME} (
                        station,
                        timestamp,
                        temperature_c,
                        humidity_pct
                    )
                    VALUES %s
                    ON CONFLICT (station, timestamp)
                    DO UPDATE SET
                        temperature_c = EXCLUDED.temperature_c,
                        humidity_pct = EXCLUDED.humidity_pct,
                        ingested_at = NOW()
                    """,
                    rows,
                )

    return len(records)


def run() -> None:
    config = get_config()
    logger.info("starting pipeline")
    records = fetch_records()
    logger.info("fetched %d records", len(records))

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
