import os
import time
import socket
import urllib.request
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

import database
from monitor import NetworkMonitor


app = Flask(__name__)
monitor = NetworkMonitor()


# ============================================================
# START MONITOR
# ============================================================

@app.before_request
def ensure_monitor_started():
    if not monitor.is_alive():
        monitor.start()


# ============================================================
# MAIN PAGE
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')


# ============================================================
# STATUS API
# ============================================================

@app.route('/api/status', methods=['GET'])
def get_status():
    metrics = database.get_latest_metrics(limit=1)

    current = metrics[0] if metrics else {
        'status': 'UNKNOWN',
        'latency': None,
        'packet_loss': 100,
        'dns_time': None,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

    stats_today = database.get_statistics(days=1)

    is_online = current['status'] == 'ONLINE'

    health_score = monitor.calculate_health_score(
        latency=current.get('latency'),
        packet_loss=current.get('packet_loss', 0),
        dns_time=current.get('dns_time'),
        is_online=is_online
    )

    now = datetime.now(timezone.utc)
    session_duration_sec = int(
        (now - monitor.session_start).total_seconds()
    )

    return jsonify({
        'status': current['status'],
        'latency': current.get('latency'),
        'packet_loss': current.get('packet_loss'),
        'dns_time': current.get('dns_time'),
        'timestamp': current.get('timestamp'),
        'health_score': health_score,
        'reliability_today': stats_today['uptime_percentage'],
        'session_duration_seconds': session_duration_sec
    })


# ============================================================
# LIVE METRICS
# ============================================================

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    settings = database.get_settings()

    try:
        limit = int(settings.get('max_graph_points', 30))
    except (ValueError, TypeError):
        limit = 30

    metrics = database.get_latest_metrics(limit=limit)

    return jsonify(metrics)


# ============================================================
# OUTAGES
# ============================================================

@app.route('/api/outages', methods=['GET'])
def get_outages():
    limit = request.args.get('limit', default=20, type=int)

    # Prevent ridiculous values
    limit = max(1, min(limit, 100))

    outages = database.get_recent_outages(limit=limit)

    return jsonify(outages)


# ============================================================
# STATISTICS
# ============================================================

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    days = request.args.get('days', default=1, type=int)

    # Keep the API within the UI's supported range
    days = max(1, min(days, 30))

    stats = database.get_statistics(days=days)

    return jsonify(stats)


# ============================================================
# SETTINGS
# ============================================================

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():

    if request.method == 'POST':

        data = request.get_json(silent=True) or {}

        valid_keys = [
            'interval',
            'ping_target',
            'dns_target',
            'retention_days',
            'max_graph_points'
        ]

        for key in valid_keys:

            if key not in data:
                continue

            val = str(data[key]).strip()

            # Numeric settings
            if key in [
                'interval',
                'retention_days',
                'max_graph_points'
            ]:

                try:
                    num = int(val)
                except ValueError:
                    continue

                if num <= 0:
                    continue

                # Sensible limits
                if key == 'interval':
                    num = max(1, min(num, 60))

                elif key == 'retention_days':
                    num = max(1, min(num, 90))

                elif key == 'max_graph_points':
                    num = max(10, min(num, 100))

                val = str(num)

            # Text settings
            elif key in ['ping_target', 'dns_target']:

                if not val:
                    continue

            database.update_setting(key, val)

        return jsonify({
            'status': 'success',
            'settings': database.get_settings()
        })

    return jsonify(database.get_settings())


# ============================================================
# REAL DOWNLOAD SPEED TEST
# ============================================================

@app.route('/api/speedtest', methods=['POST'])
def run_speedtest():

    # --------------------------------------------------------
    # Configuration
    # --------------------------------------------------------

    # Cloudflare's speed-test download endpoint.
    # 25 MB gives the connection enough data to measure properly.
    TEST_URL = "https://speed.cloudflare.com/__down?bytes=25000000"

    # Maximum duration of the test.
    TEST_DURATION = 8.0

    # Read data in chunks.
    CHUNK_SIZE = 64 * 1024  # 64 KB

    bytes_downloaded = 0

    start_time = time.perf_counter()

    try:

        request_obj = urllib.request.Request(
            TEST_URL,
            headers={
                "User-Agent": "InternetBlackBox/1.0"
            }
        )

        with urllib.request.urlopen(
            request_obj,
            timeout=12
        ) as response:

            while True:

                # Stop after the configured test duration.
                elapsed = time.perf_counter() - start_time

                if elapsed >= TEST_DURATION:
                    break

                chunk = response.read(CHUNK_SIZE)

                if not chunk:
                    break

                bytes_downloaded += len(chunk)

        elapsed = time.perf_counter() - start_time

        # Protect against extremely tiny elapsed times.
        elapsed = max(elapsed, 0.001)

        # ----------------------------------------------------
        # Calculate speed
        # ----------------------------------------------------

        speed_mbps = (
            bytes_downloaded * 8
        ) / (
            elapsed * 1_000_000
        )

        speed_mbps = round(speed_mbps, 2)

        return jsonify({
            'status': 'success',
            'download_speed_mbps': speed_mbps,
            'duration_seconds': round(elapsed, 2),
            'bytes_received': bytes_downloaded,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'test_size_mb': round(
                bytes_downloaded / (1024 * 1024),
                2
            ),
            'note': '8-second sustained download speed test'
        })

    except Exception as e:

        elapsed = time.perf_counter() - start_time

        return jsonify({
            'status': 'error',
            'message': str(e),
            'duration_seconds': round(elapsed, 2),
            'bytes_received': bytes_downloaded
        }), 500


# ============================================================
# APPLICATION START
# ============================================================

if __name__ == '__main__':

    database.init_db()

    if not monitor.is_alive():
        monitor.start()

    app.run(
        host='127.0.0.1',
        port=5000,
        debug=False
    )
