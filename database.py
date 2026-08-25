import sqlite3
import os
from datetime import datetime, timedelta, timezone

DB_DIR = os.path.join(os.path.dirname(__file__), 'data')
DB_PATH = os.path.join(DB_DIR, 'blackbox.db')

DEFAULT_SETTINGS = {
    'interval': '5',
    'ping_target': '8.8.8.8',
    'dns_target': 'one.one.one.one',
    'retention_days': '7',
    'max_graph_points': '30',
    'packet_loss_warning': '1.0',
    'packet_loss_poor': '5.0'
}

def get_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            latency REAL,
            packet_loss REAL,
            dns_time REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS outages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration_seconds INTEGER,
            status TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_measurements_timestamp ON measurements(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_outages_start ON outages(start_time)')

    for key, val in DEFAULT_SETTINGS.items():
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, val))

    conn.commit()
    conn.close()

def get_settings():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM settings')
    rows = cursor.fetchall()
    conn.close()
    settings = dict(DEFAULT_SETTINGS)
    for row in rows:
        settings[row['key']] = row['value']
    return settings

def update_setting(key, value):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
    conn.commit()
    conn.close()

def insert_measurement(status, latency, packet_loss, dns_time):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute('''
        INSERT INTO measurements (timestamp, status, latency, packet_loss, dns_time)
        VALUES (?, ?, ?, ?, ?)
    ''', (now, status, latency, packet_loss, dns_time))
    conn.commit()
    conn.close()

def start_outage():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM outages WHERE status = "ONGOING"')
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return existing['id']
    
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute('''
        INSERT INTO outages (start_time, status)
        VALUES (?, "ONGOING")
    ''', (now,))
    outage_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return outage_id

def resolve_outage(outage_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT start_time FROM outages WHERE id = ?', (outage_id,))
    row = cursor.fetchone()
    if row:
        start_time = datetime.fromisoformat(row['start_time'])
        now = datetime.now(timezone.utc)
        duration = int((now - start_time).total_seconds())
        now_str = now.isoformat()
        cursor.execute('''
            UPDATE outages
            SET end_time = ?, duration_seconds = ?, status = "RESOLVED"
            WHERE id = ?
        ''', (now_str, duration, outage_id))
        conn.commit()
    conn.close()

def cleanup_old_data(retention_days):
    conn = get_connection()
    cursor = conn.cursor()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=int(retention_days))).isoformat()
    cursor.execute('DELETE FROM measurements WHERE timestamp < ?', (cutoff,))
    cursor.execute('DELETE FROM outages WHERE start_time < ? AND status = "RESOLVED"', (cutoff,))
    conn.commit()
    conn.close()

def get_latest_metrics(limit=30):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT timestamp, status, latency, packet_loss, dns_time
        FROM measurements
        ORDER BY id DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in reversed(rows)]

def get_recent_outages(limit=20):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, start_time, end_time, duration_seconds, status
        FROM outages
        ORDER BY id DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_statistics(days=1):
    conn = get_connection()
    cursor = conn.cursor()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    cursor.execute('''
        SELECT 
            COUNT(*) as total_checks,
            SUM(CASE WHEN status = 'ONLINE' THEN 1 ELSE 0 END) as online_checks,
            AVG(CASE WHEN status = 'ONLINE' THEN latency END) as avg_latency,
            MIN(CASE WHEN status = 'ONLINE' THEN latency END) as min_latency,
            MAX(CASE WHEN status = 'ONLINE' THEN latency END) as max_latency,
            AVG(CASE WHEN status = 'ONLINE' THEN packet_loss END) as avg_packet_loss,
            AVG(CASE WHEN status = 'ONLINE' THEN dns_time END) as avg_dns_time
        FROM measurements
        WHERE timestamp >= ?
    ''', (cutoff,))
    stats_row = cursor.fetchone()

    cursor.execute('''
        SELECT COUNT(*) as outage_count, MAX(duration_seconds) as max_duration, SUM(duration_seconds) as total_downtime
        FROM outages
        WHERE start_time >= ?
    ''', (cutoff,))
    outage_row = cursor.fetchone()
    conn.close()

    total_checks = stats_row['total_checks'] or 0
    online_checks = stats_row['online_checks'] or 0
    uptime_pct = (online_checks / total_checks * 100) if total_checks > 0 else 100.0

    return {
        'total_checks': total_checks,
        'uptime_percentage': round(uptime_pct, 2),
        'avg_latency': round(stats_row['avg_latency'] or 0, 2),
        'min_latency': round(stats_row['min_latency'] or 0, 2),
        'max_latency': round(stats_row['max_latency'] or 0, 2),
        'avg_packet_loss': round(stats_row['avg_packet_loss'] or 0, 2),
        'avg_dns_time': round(stats_row['avg_dns_time'] or 0, 2),
        'outage_count': outage_row['outage_count'] or 0,
        'longest_outage_sec': outage_row['max_duration'] or 0,
        'total_downtime_sec': outage_row['total_downtime'] or 0
    }