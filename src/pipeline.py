"""Week 6 assignment: Azure-deployed data pipeline."""

import logging
import os
import json
from datetime import date

import psycopg2
from azure.storage.blob import BlobServiceClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Quiet Azure logs
logging.getLogger("azure").setLevel(logging.WARNING)


# ----------------------------
# CONFIG
# ----------------------------
def get_config() -> dict:
    postgres_url = os.getenv("POSTGRES_URL")
    blob_conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    source_name = os.getenv("SOURCE_NAME", "weather")

    if not blob_conn:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is missing")

    # Postgres is optional now (won't crash pipeline)
    return {
        "postgres_url": postgres_url,
        "azure_storage_connection_string": blob_conn,
        "source_name": source_name,
    }


# ----------------------------
# DATA
# ----------------------------
def fetch_records() -> list[dict]:
    return [
        {
            "station": "Amsterdam",
            "timestamp": date.today().isoformat(),
            "temperature_c": 18.5,
            "humidity_pct": 72,
        }
    ]


# ----------------------------
# BLOB STORAGE (TASK 1)
# ----------------------------
def upload_raw_to_blob(records: list[dict], blob_conn_str: str, source: str) -> str:
    today = date.today().isoformat()
    blob_name = f"{source}/{today}.json"

    blob_service = BlobServiceClient.from_connection_string(blob_conn_str)
    blob_client = blob_service.get_blob_client(
        container="raw",
        blob=blob_name
    )

    data = json.dumps(records).encode("utf-8")
    blob_client.upload_blob(data, overwrite=True)

    return blob_name


# ----------------------------
# POSTGRES (OPTIONAL)
# ----------------------------
def write_to_postgres(records: list[dict], postgres_url: str) -> int:
    if not postgres_url:
        raise RuntimeError("POSTGRES_URL not configured")

    conn = psycopg2.connect(postgres_url)
    cur = conn.cursor()

    cur.execute("CREATE SCHEMA IF NOT EXISTS dev_muna")
    cur.execute("SET search_path TO dev_muna")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS weather_readings (
            id SERIAL PRIMARY KEY,
            station TEXT,
            timestamp TEXT,
            temperature_c FLOAT,
            humidity_pct FLOAT
        )
    """)

    count = 0

    for r in records:
        cur.execute("""
            INSERT INTO weather_readings
            (station, timestamp, temperature_c, humidity_pct)
            VALUES (%s, %s, %s, %s)
        """, (
            r["station"],
            r["timestamp"],
            r["temperature_c"],
            r["humidity_pct"]
        ))
        count += 1

    conn.commit()
    cur.close()
    conn.close()

    return count


# ----------------------------
# RUN PIPELINE
# ----------------------------
def run() -> None:
    config = get_config()
    logger.info("starting pipeline")

    records = fetch_records()

    # Upload to Blob (TASK 1)
    blob_name = upload_raw_to_blob(
        records,
        config["azure_storage_connection_string"],
        config["source_name"],
    )
    logger.info("uploaded blob %s", blob_name)

    # Postgres optional (won't break pipeline)
    try:
        row_count = write_to_postgres(records, config["postgres_url"])
        logger.info("wrote %d rows to postgres", row_count)
    except Exception as e:
        logger.warning("postgres skipped: %s", e)

    logger.info("pipeline complete (today=%s)", date.today().isoformat())


if __name__ == "__main__":
    run()