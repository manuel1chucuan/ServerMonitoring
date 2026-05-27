from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Mazatlan")
VALID_RANGES = frozenset({"hour", "day", "month", "year"})

CHART_BUCKETS = {
    "hour": None,
    "day": "hour",
    "month": "day",
    "year": "month",
}


@dataclass(frozen=True)
class TimeWindow:
    range_key: str
    start_utc: datetime
    end_utc: datetime
    chart_bucket: str | None
    label: str
    crosses_midnight: bool = False


def now_local() -> datetime:
    return datetime.now(TZ)


def _parse_date(value: str | None) -> date:
    if not value:
        return now_local().date()
    return date.fromisoformat(value)


def _parse_month(value: str | None) -> tuple[int, int]:
    if value:
        year_str, month_str = value.split("-", 1)
        return int(year_str), int(month_str)
    local = now_local()
    return local.year, local.month


def _parse_year(value: str | None) -> int:
    if value:
        return int(value)
    return now_local().year


def _parse_time(value: str | None, default: time) -> time:
    if not value:
        return default
    parts = value.split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return time(hour=hour, minute=minute)


def _local_to_utc(dt_local: datetime) -> datetime:
    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=TZ)
    return dt_local.astimezone(timezone.utc)


def _month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def resolve_window(
    range_key: str,
    *,
    date_str: str | None = None,
    month_str: str | None = None,
    year_str: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> TimeWindow:
    if range_key not in VALID_RANGES:
        raise ValueError(f"Rango invalido: {range_key}")

    if range_key == "hour":
        day = _parse_date(date_str)
        local_now = now_local()
        default_start = time(local_now.hour, 0)
        default_end = time((local_now.hour + 1) % 24, 0)

        start_t = _parse_time(start_time, default_start)
        start_local = datetime.combine(day, start_t, tzinfo=TZ)

        if end_time:
            end_t = _parse_time(end_time, default_end)
            end_local = datetime.combine(day, end_t, tzinfo=TZ)
            crosses = end_local <= start_local
            if crosses:
                end_local += timedelta(days=1)
        else:
            end_local = start_local + timedelta(hours=1)
            crosses = end_local.date() > day
            end_t = end_local.time()

        label = (
            f"{day.isoformat()} {start_t.strftime('%H:%M')}–"
            f"{end_t.strftime('%H:%M')} Mazatlan"
            + (" (+1 dia)" if crosses else "")
        )
        return TimeWindow(
            range_key=range_key,
            start_utc=_local_to_utc(start_local),
            end_utc=_local_to_utc(end_local),
            chart_bucket=CHART_BUCKETS[range_key],
            label=label,
            crosses_midnight=crosses,
        )

    if range_key == "day":
        day = _parse_date(date_str)
        start_local = datetime.combine(day, time.min, tzinfo=TZ)
        end_local = start_local + timedelta(days=1)
        label = f"dia {day.isoformat()} (Mazatlan)"
        return TimeWindow(
            range_key=range_key,
            start_utc=_local_to_utc(start_local),
            end_utc=_local_to_utc(end_local),
            chart_bucket=CHART_BUCKETS[range_key],
            label=label,
        )

    if range_key == "month":
        year, month = _parse_month(month_str)
        start_local = datetime(year, month, 1, tzinfo=TZ)
        end_local = datetime.combine(_month_end(year, month), time.min, tzinfo=TZ)
        label = f"mes {year}-{month:02d} (Mazatlan)"
        return TimeWindow(
            range_key=range_key,
            start_utc=_local_to_utc(start_local),
            end_utc=_local_to_utc(end_local),
            chart_bucket=CHART_BUCKETS[range_key],
            label=label,
        )

    year = _parse_year(year_str)
    start_local = datetime(year, 1, 1, tzinfo=TZ)
    end_local = datetime(year + 1, 1, 1, tzinfo=TZ)
    label = f"anio {year} (Mazatlan)"
    return TimeWindow(
        range_key=range_key,
        start_utc=_local_to_utc(start_local),
        end_utc=_local_to_utc(end_local),
        chart_bucket=CHART_BUCKETS[range_key],
        label=label,
    )
