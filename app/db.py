import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

from app.ranges import TimeWindow, resolve_window

DATABASE_URL = os.environ["DATABASE_URL"]


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


def get_available_years() -> list[int]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT EXTRACT(YEAR FROM recorded_at AT TIME ZONE 'America/Mazatlan')::int AS y
                FROM server_metrics
                ORDER BY y DESC
                """
            )
            years = [row[0] for row in cur.fetchall()]
    if not years:
        from app.ranges import now_local

        years = [now_local().year]
    return years


def _query_window(window: TimeWindow, limit: int = 500) -> tuple[list[dict], list[dict], dict]:
    params = (window.start_utc, window.end_utc, limit)
    range_clause = "recorded_at >= %s AND recorded_at < %s"

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*)::int AS sample_count,
                    ROUND(AVG(cpu_percent)::numeric, 2) AS cpu_percent,
                    ROUND(AVG(ram_percent)::numeric, 2) AS ram_percent,
                    ROUND(AVG(ram_used_mb)::numeric, 0) AS ram_used_mb,
                    ROUND(AVG(disk_percent)::numeric, 2) AS disk_percent,
                    ROUND(AVG(disk_used_gb)::numeric, 2) AS disk_used_gb,
                    ROUND(AVG(temp_celsius)::numeric, 2) AS temp_celsius
                FROM server_metrics
                WHERE {range_clause}
                """,
                (window.start_utc, window.end_utc),
            )
            averages = dict(cur.fetchone() or {"sample_count": 0})

            if window.chart_bucket is None:
                cur.execute(
                    f"""
                    SELECT
                        recorded_at,
                        cpu_percent,
                        ram_percent,
                        disk_percent,
                        temp_celsius
                    FROM server_metrics
                    WHERE {range_clause}
                    ORDER BY recorded_at ASC
                    LIMIT %s
                    """,
                    params,
                )
            else:
                cur.execute(
                    f"""
                    SELECT
                        date_trunc(%s, recorded_at AT TIME ZONE 'America/Mazatlan')
                            AT TIME ZONE 'America/Mazatlan' AS recorded_at,
                        ROUND(AVG(cpu_percent)::numeric, 2) AS cpu_percent,
                        ROUND(AVG(ram_percent)::numeric, 2) AS ram_percent,
                        ROUND(AVG(disk_percent)::numeric, 2) AS disk_percent,
                        ROUND(AVG(temp_celsius)::numeric, 2) AS temp_celsius
                    FROM server_metrics
                    WHERE {range_clause}
                    GROUP BY 1
                    ORDER BY 1 ASC
                    LIMIT %s
                    """,
                    (window.chart_bucket, window.start_utc, window.end_utc, limit),
                )
            series = [dict(row) for row in cur.fetchall()]

            cur.execute(
                f"""
                SELECT *
                FROM server_metrics
                WHERE {range_clause}
                ORDER BY recorded_at DESC
                LIMIT %s
                """,
                params,
            )
            rows = [dict(row) for row in cur.fetchall()]

    return series, rows, averages


def get_stats(**filter_params) -> dict:
    window = resolve_window(**filter_params)
    series, rows, averages = _query_window(window)
    return {
        "range": window.range_key,
        "window": {
            "label": window.label,
            "start_utc": window.start_utc.isoformat(),
            "end_utc": window.end_utc.isoformat(),
            "crosses_midnight": window.crosses_midnight,
        },
        "averages": averages,
        "series": series,
        "rows": rows,
    }
