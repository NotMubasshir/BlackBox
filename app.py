import os
import time
import socket
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template, request
import database
from monitor import NetworkMonitor

app = Flask(__name__)
monitor = NetworkMonitor()

@app.before_request
def ensure_monitor_started():
    if not monitor.is_alive():
        monitor.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    metrics = database.get_latest_metrics(limit=1)
    current = metrics[0] if metrics else {
        'status': 'UNKNOWN',
        'latency': 0,
        'packet_loss': 0,
        'dns_time': 0,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

    stats_today = database.get_statistics(days=1)
    is_online = (current['status'] == 'ONLINE')
    
    health_score = monitor.calculate_health_score(
        latency=current.get('latency'),
        packet_loss=current.get('packet_loss', 0),
        dns_time=current.get('dns_time'),
        is_online=is_online
    )

    now = datetime.now(timezone.utc)
    session_duration_sec = int((now - monitor.session_start).total_seconds())

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

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    settings = database.get_settings()
    limit = int(settings.get('max_graph_points', 30))
    metrics = database.get_latest_metrics(limit=limit)
    return jsonify(metrics)

@app.route('/api/outages', methods=['GET'])
def get_outages():
    limit = request.args.get('limit', default=20, type=int)
    outages = database.get_recent_outages(limit=limit)
    return jsonify(outages)

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    days = request.args.get('days', default=1, type=int)
    stats = database.get_statistics(days=days)
    return jsonify(stats)

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        data = request.json or {}
        valid_keys = ['interval', 'ping_target', 'dns_target', 'retention_days', 'max_graph_points']
        
        for key in valid_keys:
            if key in data:
                val = str(data[key]).strip()
                if key in ['interval', 'retention_days', 'max_graph_points']:
                    try:
                        num = int(val)
                        if num <= 0:
                            continue
                    except ValueError:
                        continue
                database.update_setting(key, val)

        return jsonify({'status': 'success', 'settings': database.get_settings()})
    else:
        return jsonify(database.get_settings())

@app.route('/api/speedtest', methods=['POST'])
def run_speedtest():
    test_host = "1.1.1.1"
    port = 80
    start_time = time.perf_counter()
    bytes_downloaded = 0
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((test_host, port))
        request_header = f"GET / HTTP/1.1\r\nHost: {test_host}\r\nUser-Agent: BlackBox/1.0\r\nConnection: close\r\n\r\n"
        sock.sendall(request_header.encode())

        while True:
            data = sock.recv(4096)
            if not data:
                break
            bytes_downloaded += len(data)
        sock.close()
        
        elapsed = time.perf_counter() - start_time
        if elapsed > 0 and bytes_downloaded > 0:
            speed_mbps = round((bytes_downloaded * 8) / (elapsed * 1_000_000), 2)
        else:
            speed_mbps = 0.0

        return jsonify({
            'status': 'success',
            'download_speed_mbps': speed_mbps,
            'duration_seconds': round(elapsed, 2),
            'bytes_received': bytes_downloaded,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'note': 'Standard lightweight HTTP GET probe test'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Speed test failed: {str(e)}'
        }), 500

if __name__ == '__main__':
    database.init_db()
    if not monitor.is_alive():
        monitor.start()
    app.run(host='127.0.0.1', port=5000, debug=False)