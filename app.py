import time
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

import database
from monitor import NetworkMonitor

app = Flask(__name__)

_monitor_lock = threading.Lock()
monitor = None


def ensure_monitor_started():
    global monitor

    with _monitor_lock:
        if monitor is None or not monitor.is_alive():
            monitor = NetworkMonitor()
            monitor.start()

        return monitor


# Make sure the database exists before requests begin.
database.init_db()
ensure_monitor_started()


@app.before_request
def before_request():
    ensure_monitor_started()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def get_status():
    metrics = database.get_latest_metrics(limit=1)

    current = metrics[0] if metrics else {
        "status": "UNKNOWN",
        "latency": None,
        "packet_loss": None,
        "dns_time": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    stats_today = database.get_statistics(days=1)

    is_online = current.get("status") == "ONLINE"

    active_monitor = ensure_monitor_started()

    health_score = active_monitor.calculate_health_score(
        latency=current.get("latency"),
        packet_loss=current.get("packet_loss") or 0,
        dns_time=current.get("dns_time"),
        is_online=is_online,
    )

    now = datetime.now(timezone.utc)

    session_duration = int(
        (now - active_monitor.session_start).total_seconds()
    )

    return jsonify({
        "status": current.get("status", "UNKNOWN"),
        "latency": current.get("latency"),
        "packet_loss": current.get("packet_loss"),
        "dns_time": current.get("dns_time"),
        "timestamp": current.get("timestamp"),
        "health_score": health_score,
        "reliability_today": stats_today["uptime_percentage"],
        "session_duration_seconds": session_duration,
    })


@app.route("/api/metrics")
def get_metrics():
    settings = database.get_settings()

    limit = int(
        settings.get("max_graph_points", 40)
    )

    return jsonify(
        database.get_latest_metrics(limit=limit)
    )


@app.route("/api/outages")
def get_outages():
    limit = request.args.get(
        "limit",
        default=20,
        type=int
    )

    limit = max(1, min(limit, 100))

    return jsonify(
        database.get_recent_outages(limit=limit)
    )


@app.route("/api/statistics")
def get_statistics():
    days = request.args.get(
        "days",
        default=1,
        type=int
    )

    days = max(1, min(days, 30))

    return jsonify(
        database.get_statistics(days=days)
    )


@app.route("/api/settings", methods=["GET", "POST"])
def handle_settings():

    if request.method == "GET":
        return jsonify(
            database.get_settings()
        )

    data = request.get_json(
        silent=True
    ) or {}

    errors = []

    numeric_rules = {
        "interval": (1, 60),
        "retention_days": (1, 90),
        "max_graph_points": (10, 100),
    }

    for key, (minimum, maximum) in numeric_rules.items():

        if key not in data:
            continue

        try:
            value = int(data[key])

            if not minimum <= value <= maximum:
                raise ValueError

            database.update_setting(
                key,
                value
            )

        except (TypeError, ValueError):
            errors.append(
                f"{key} must be between "
                f"{minimum} and {maximum}."
            )

    for key in (
        "ping_target",
        "dns_target",
        "dns_probe_domain",
    ):

        if key not in data:
            continue

        value = str(
            data[key]
        ).strip()

        if not value:
            errors.append(
                f"{key} cannot be empty."
            )

        elif len(value) > 255:
            errors.append(
                f"{key} is too long."
            )

        else:
            database.update_setting(
                key,
                value
            )

    if errors:
        return jsonify({
            "status": "error",
            "errors": errors,
        }), 400

    return jsonify({
        "status": "success",
        "settings": database.get_settings(),
    })


@app.route("/api/speedtest", methods=["POST"])
def run_speedtest():

    """
    Sustained download test.

    The old implementation requested:

        http://1.1.1.1/

    That isn't a bandwidth-test file and can return 403.

    This version uses Cloudflare's dedicated speed-test
    download endpoint instead.
    """

    test_duration = 10.0
    max_bytes = 200 * 1024 * 1024
    chunk_size = 64 * 1024

    total_bytes = 0

    start = time.perf_counter()

    last_error = None

    try:

        while (
            time.perf_counter() - start < test_duration
            and total_bytes < max_bytes
        ):

            remaining = max_bytes - total_bytes

            request_url = (
                "https://speed.cloudflare.com/"
                "__down?bytes="
                f"{min(25_000_000, remaining)}"
            )

            req = urllib.request.Request(
                request_url,
                headers={
                    "User-Agent":
                        "InternetBlackBox/2.0",

                    "Accept":
                        "*/*",

                    "Cache-Control":
                        "no-cache",
                },
                method="GET",
            )

            try:

                with urllib.request.urlopen(
                    req,
                    timeout=8
                ) as response:

                    while (
                        time.perf_counter() - start
                        < test_duration
                        and total_bytes < max_bytes
                    ):

                        chunk = response.read(
                            chunk_size
                        )

                        if not chunk:
                            break

                        total_bytes += len(chunk)

            except (
                urllib.error.URLError,
                TimeoutError,
                OSError
            ) as exc:

                last_error = str(exc)

                break

        elapsed = max(
            time.perf_counter() - start,
            0.001
        )

        if total_bytes <= 0:

            return jsonify({
                "status": "error",
                "message":
                    "No test data was received. "
                    + (
                        last_error
                        or
                        "The speed-test server did not respond."
                    ),
            }), 502

        speed_mbps = (
            total_bytes * 8
        ) / elapsed / 1_000_000

        active_monitor = ensure_monitor_started()

        ping = active_monitor.measure_ping(
            "1.1.1.1"
        )

        return jsonify({
            "status": "success",

            "download_speed_mbps":
                round(speed_mbps, 2),

            "duration_seconds":
                round(elapsed, 2),

            "bytes_received":
                total_bytes,

            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "latency_ms":
                (
                    round(ping, 2)
                    if ping is not None
                    else None
                ),

            "server":
                "Cloudflare edge",

            "test_type":
                "sustained HTTP download",
        })

    except Exception as exc:

        return jsonify({
            "status": "error",
            "message":
                f"Speed test failed: {exc}",
        }), 500


if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        threaded=True,
    )
