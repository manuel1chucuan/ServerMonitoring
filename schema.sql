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

CREATE INDEX IF NOT EXISTS idx_server_metrics_recorded_at
    ON server_metrics (recorded_at DESC);
