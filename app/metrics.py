import os
import time
from pathlib import Path


def _proc_path(name: str) -> Path:
    base = Path(os.environ.get("HOST_PROC", "/proc"))
    return base / name


def _sys_path(*parts: str) -> Path:
    base = Path(os.environ.get("HOST_SYS", "/sys"))
    return base.joinpath(*parts)


def _disk_path() -> str:
    return os.environ.get("HOST_ROOT", "/")


def read_cpu_percent(sample_seconds: float = 0.5) -> float:
    def snapshot():
        line = _proc_path("stat").read_text().splitlines()[0].split()
        values = [int(x) for x in line[1:8]]
        idle = values[3] + values[4]
        total = sum(values)
        return idle, total

    idle_a, total_a = snapshot()
    time.sleep(sample_seconds)
    idle_b, total_b = snapshot()

    idle_delta = idle_b - idle_a
    total_delta = total_b - total_a
    if total_delta <= 0:
        return 0.0
    usage = (1.0 - idle_delta / total_delta) * 100.0
    return round(max(0.0, min(100.0, usage)), 2)


def read_memory() -> tuple[float, int, int]:
    data: dict[str, int] = {}
    for line in _proc_path("meminfo").read_text().splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith(":"):
            key = parts[0][:-1]
            data[key] = int(parts[1])

    total_kb = data.get("MemTotal", 0)
    available_kb = data.get("MemAvailable", data.get("MemFree", 0))
    used_kb = max(0, total_kb - available_kb)
    percent = round((used_kb / total_kb) * 100.0, 2) if total_kb else 0.0
    return percent, used_kb // 1024, total_kb // 1024


def read_disk() -> tuple[float, float, float]:
    import shutil

    usage = shutil.disk_usage(_disk_path())
    total_gb = usage.total / (1024**3)
    used_gb = usage.used / (1024**3)
    percent = round((usage.used / usage.total) * 100.0, 2) if usage.total else 0.0
    return percent, round(used_gb, 2), round(total_gb, 2)


def read_temperature_c() -> float | None:
    thermal_dir = _sys_path("class", "thermal")
    if not thermal_dir.is_dir():
        return None

    preferred: list[float] = []
    fallback: list[float] = []

    for zone in sorted(thermal_dir.glob("thermal_zone*")):
        temp_file = zone / "temp"
        type_file = zone / "type"
        if not temp_file.is_file():
            continue
        try:
            millidegrees = int(temp_file.read_text().strip())
        except (OSError, ValueError):
            continue
        if millidegrees <= 0:
            continue
        celsius = millidegrees / 1000.0
        zone_type = type_file.read_text().strip() if type_file.is_file() else ""
        if zone_type in {"x86_pkg_temp", "TCPU", "acpitz"}:
            preferred.append(celsius)
        else:
            fallback.append(celsius)

    values = preferred or fallback
    if not values:
        return None
    return round(max(values), 2)


def collect_snapshot() -> dict:
    ram_percent, ram_used_mb, ram_total_mb = read_memory()
    disk_percent, disk_used_gb, disk_total_gb = read_disk()
    return {
        "cpu_percent": read_cpu_percent(),
        "ram_percent": ram_percent,
        "ram_used_mb": ram_used_mb,
        "ram_total_mb": ram_total_mb,
        "disk_percent": disk_percent,
        "disk_used_gb": disk_used_gb,
        "disk_total_gb": disk_total_gb,
        "temp_celsius": read_temperature_c(),
    }
