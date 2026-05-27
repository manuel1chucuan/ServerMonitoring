import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ["DATABASE_URL"]

RANGE_WINDOWS = {
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(days=7),
    "month": timedelta(days=30),
}

CHART_BUCKETS = {
    "hour": None,
    "day": None,
    "week": "hour",
    "month": "day",
}


def init_db() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS server_metrics (
                    id BIGSERIAL PRIMARY KEY,
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    cpu_percent NUMERIC(5, 2) NOT NULL,
                    ram_percent NUMERIC(5, 2) NOT NULL,
                    ram_used_mb BIGINT NOT NULL,
                    ram_total_mb BIGINT NOT NULL,
                    disk_percent NUMERIC(5, 2) NOT NULL,
                    disk_used_gb NUMERIC(10, 2) NOT NULL,
                    disk_total_gb NUMERIC(10, 2) NOT NULL,
                    temp_celsius NUMERIC(5, 2)
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_server_metrics_recorded_at
                ON server_metrics (recorded_at DESC);
                """
            )
        conn.commit()


@contextmanager
def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


def insert_metrics(snapshot: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO server_metrics (
                    recorded_at, cpu_percent, ram_percent, ram_used_mb, ram_total_mb,
                    disk_percent, disk_used_gb, disk_total_gb, temp_celsius
                ) VALUES (
                    NOW(), %(cpu_percent)s, %(ram_percent)s, %(ram_used_mb)s, %(ram_total_mb)s,
                    %(disk_percent)s, %(disk_used_gb)s, %(disk_total_gb)s, %(temp_celsius)s
                )
                """,
                snapshot,
            )
        conn.commit()


def get_latest() -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM server_metrics
                ORDER BY recorded_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
    return dict(row) if row else None


def _validate_range(range_key: str) -> datetime:
    if range_key not in RANGE_WINDOWS:
        raise ValueError(f"Rango invalido: {range_key}")
    return datetime.now(timezone.utc) - RANGE_WINDOWS[range_key]


def get_history(range_key: str, limit: int = 500) -> list[dict]:
    since = _validate_range(range_key)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM server_metrics
                WHERE recorded_at >= %s
                ORDER BY recorded_at DESC
                LIMIT %s
                """,
                (since, limit),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def get_averages(range_key: str) -> dict:
    since = _validate_range(range_key)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)::int AS sample_count,
                    ROUND(AVG(cpu_percent)::numeric, 2) AS cpu_percent,
                    ROUND(AVG(ram_percent)::numeric, 2) AS ram_percent,
                    ROUND(AVG(ram_used_mb)::numeric, 0) AS ram_used_mb,
                    ROUND(AVG(disk_percent)::numeric, 2) AS disk_percent,
                    ROUND(AVG(disk_used_gb)::numeric, 2) AS disk_used_gb,
                    ROUND(AVG(temp_celsius)::numeric, 2) AS temp_celsius
                FROM server_metrics
                WHERE recorded_at >= %s
                """,
                (since,),
            )
            row = cur.fetchone()
    return dict(row) if row else {"sample_count": 0}


def get_chart_series(range_key: str, limit: int = 500) -> list[dict]:
    since = _validate_range(range_key)
    bucket = CHART_BUCKETS[range_key]

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if bucket is None:
                cur.execute(
                    """
                    SELECT
                        recorded_at,
                        cpu_percent,
                        ram_percent,
                        disk_percent,
                        temp_celsius
                    FROM server_metrics
                    WHERE recorded_at >= %s
                    ORDER BY recorded_at ASC
                    LIMIT %s
                    """,
                    (since, limit),
                )
            else:
                cur.execute(
                    f"""
                    SELECT
                        date_trunc(%s, recorded_at) AS recorded_at,
                        ROUND(AVG(cpu_percent)::numeric, 2) AS cpu_percent,
                        ROUND(AVG(ram_percent)::numeric, 2) AS ram_percent,
                        ROUND(AVG(disk_percent)::numeric, 2) AS disk_percent,
                        ROUND(AVG(temp_celsius)::numeric, 2) AS temp_celsius
                    FROM server_metrics
                    WHERE recorded_at >= %s
                    GROUP BY 1
                    ORDER BY 1 ASC
                    LIMIT %s
                    """,
                    (bucket, since, limit),
                )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def get_stats(range_key: str) -> dict:
    return {
        "range": range_key,
        "averages": get_averages(range_key),
        "series": get_chart_series(range_key),
        "rows": get_history(range_key),
    }
