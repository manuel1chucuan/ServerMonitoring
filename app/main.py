import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template, request

from app import db
from app.metrics import collect_snapshot

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


@app.route("/api/history")
def api_history():
    range_key = request.args.get("range", "hour")
    try:
        rows = db.get_history(range_key)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"range": range_key, "count": len(rows), "rows": rows})


def create_app() -> Flask:
    wait_for_database()
    record_metrics()
    interval_minutes = int(os.environ.get("COLLECT_INTERVAL_MINUTES", "5"))
    scheduler.add_job(record_metrics, "interval", minutes=interval_minutes, id="collect_metrics")
    scheduler.start()
    return app


application = create_app()
