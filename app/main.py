import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template, request

from app import db
from app.metrics import collect_snapshot
from app.ranges import now_local

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("servermonitor")

app = Flask(__name__, template_folder="../templates", static_folder="../static")
scheduler = BackgroundScheduler(timezone="UTC")


def record_metrics() -> None:
    snapshot = collect_snapshot()
    db.insert_metrics(snapshot)
    logger.info("Metricas registradas: %s", snapshot)


def wait_for_database(retries: int = 30, delay_seconds: float = 2.0) -> None:
    import time

    for attempt in range(1, retries + 1):
        try:
            db.init_db()
            logger.info("Base de datos lista")
            return
        except Exception as exc:
            logger.warning("Esperando base de datos (%s/%s): %s", attempt, retries, exc)
            time.sleep(delay_seconds)
    raise RuntimeError("No se pudo conectar a PostgreSQL")


def _filter_params() -> dict:
    return {
        "range_key": request.args.get("range", "hour"),
        "date_str": request.args.get("date"),
        "month_str": request.args.get("month"),
        "year_str": request.args.get("year"),
        "start_time": request.args.get("start_time"),
        "end_time": request.args.get("end_time"),
    }


@app.route("/")
def dashboard():
    return render_template("index.html")


@app.route("/api/current")
def api_current():
    latest = db.get_latest()
    if latest is None:
        snapshot = collect_snapshot()
        return jsonify({"source": "live", "metrics": snapshot})
    return jsonify({"source": "database", "metrics": latest})


@app.route("/api/meta")
def api_meta():
    local = now_local()
    return jsonify(
        {
            "timezone": "America/Mazatlan",
            "timezone_label": "Mazatlan, Sinaloa",
            "now_local": local.isoformat(),
            "today": local.date().isoformat(),
            "current_month": f"{local.year}-{local.month:02d}",
            "current_year": local.year,
            "years": db.get_available_years(),
        }
    )


@app.route("/api/stats")
def api_stats():
    try:
        stats = db.get_stats(**_filter_params())
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    stats["count"] = len(stats["rows"])
    return jsonify(stats)


def create_app() -> Flask:
    wait_for_database()
    record_metrics()
    interval_minutes = int(os.environ.get("COLLECT_INTERVAL_MINUTES", "5"))
    scheduler.add_job(record_metrics, "interval", minutes=interval_minutes, id="collect_metrics")
    scheduler.start()
    return app


application = create_app()
