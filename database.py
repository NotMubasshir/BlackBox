import os
import sqlite3
from datetime import datetime, timedelta, timezone


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DB_DIR, "blackbox.db")


DEFAULT_SETTINGS = {
    "interval": "5",
    "ping_target": "8.8.8.8",
    "dns_target": "one.one.one.one",
    "retention_days": "7",
    "max_graph_points": "30",
    "packet_loss_warning": "1.0",
    "packet_loss_poor": "5.0",
}


def utc_now():
    return datetime.now(timezone.utc)


def get_connection():
    os.makedirs(DB_DIR, exist_ok=True)

    conn = sqlite3.connect(
        DB_PATH,
        timeout=10.0,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            latency REAL,
            packet_loss REAL,
            dns_time REAL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS outages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration_seconds INTEGER,
            status TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_measurements_timestamp
        ON measurements(timestamp)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_outages_start
        ON outages(start_time)
    """)

    for key, value in DEFAULT_SETTINGS.items():
        cursor.execute(
            """
            INSERT OR IGNORE INTO settings (key, value)
            VALUES (?, ?)
            """,
            (key, value)
        )

    conn.commit()
    conn.close()


def get_settings():
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("SELECT key, value FROM settings")

        rows = cursor.fetchall()

        settings = dict(DEFAULT_SETTINGS)

        for row in rows:
            settings[row["key"]] = row["value"]

        return settings

    finally:
        conn.close()


def update_setting(key, value):
    if key not in DEFAULT_SETTINGS:
        raise ValueError(f"Unknown setting: {key}")

    conn = get_connection()

    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
            """,
            (key, str(value))
        )

        conn.commit()

    finally:
        conn.close()


def insert_measurement(
    status,
    latency,
    packet_loss,
    dns_time
):
    conn = get_connection()

    try:
        conn.execute(
            """
            INSERT INTO measurements (
                timestamp,
                status,
                latency,
                packet_loss,
                dns_time
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                utc_now().isoformat(),
                status,
                latency,
                packet_loss,
                dns_time,
            )
        )

        conn.commit()

    finally:
        conn.close()


def start_outage():
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id
            FROM outages
            WHERE status = 'ONGOING'
            ORDER BY id DESC
            LIMIT 1
        """)

        existing = cursor.fetchone()

        if existing:
            return existing["id"]

        cursor.execute(
            """
            INSERT INTO outages (
                start_time,
                status
            )
            VALUES (?, 'ONGOING')
            """,
            (utc_now().isoformat(),)
        )

        outage_id = cursor.lastrowid

        conn.commit()

        return outage_id

    finally:
        conn.close()


def resolve_outage(outage_id):
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT start_time
            FROM outages
            WHERE id = ?
            """,
            (outage_id,)
        )

        row = cursor.fetchone()

        if not row:
            return

        start_time = datetime.fromisoformat(row["start_time"])

        now = utc_now()

        duration = max(
            0,
            int((now - start_time).total_seconds())
        )

        cursor.execute(
            """
            UPDATE outages

            SET
                end_time = ?,
                duration_seconds = ?,
                status = 'RESOLVED'

            WHERE id = ?
            """,
            (
                now.isoformat(),
                duration,
                outage_id,
            )
        )

        conn.commit()

    finally:
        conn.close()


def cleanup_old_data(retention_days):
    retention_days = max(1, int(retention_days))

    cutoff = (
        utc_now() - timedelta(days=retention_days)
    ).isoformat()

    conn = get_connection()

    try:
        conn.execute(
            """
            DELETE FROM measurements
            WHERE timestamp < ?
            """,
            (cutoff,)
        )

        conn.execute(
            """
            DELETE FROM outages
            WHERE start_time < ?
              AND status = 'RESOLVED'
            """,
            (cutoff,)
        )

        conn.commit()

    finally:
        conn.close()


def get_latest_metrics(limit=30):
    limit = max(1, min(int(limit), 1000))

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                timestamp,
                status,
                latency,
                packet_loss,
                dns_time

            FROM measurements

            ORDER BY id DESC

            LIMIT ?
            """,
            (limit,)
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in reversed(rows)
        ]

    finally:
        conn.close()


def get_recent_outages(limit=20):
    limit = max(1, min(int(limit), 200))

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                start_time,
                end_time,
                duration_seconds,
                status

            FROM outages

            ORDER BY id DESC

            LIMIT ?
            """,
            (limit,)
        )

        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


def get_statistics(days=1):
    days = max(1, min(int(days), 3650))

    now = utc_now()

    cutoff = (
        now - timedelta(days=days)
    ).isoformat()

    conn = get_connection()

    try:
        cursor = conn.cursor()

        # --------------------------------------------------------
        # Measurement statistics
        # --------------------------------------------------------

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_checks,

                SUM(
                    CASE
                        WHEN status = 'ONLINE'
                        THEN 1
                        ELSE 0
                    END
                ) AS online_checks,

                AVG(
                    CASE
                        WHEN status = 'ONLINE'
                        THEN latency
                    END
                ) AS avg_latency,

                MIN(
                    CASE
                        WHEN status = 'ONLINE'
                        THEN latency
                    END
                ) AS min_latency,

                MAX(
                    CASE
                        WHEN status = 'ONLINE'
                        THEN latency
                    END
                ) AS max_latency,

                AVG(
                    CASE
                        WHEN status = 'ONLINE'
                        THEN packet_loss
                    END
                ) AS avg_packet_loss,

                AVG(
                    CASE
                        WHEN status = 'ONLINE'
                        THEN dns_time
                    END
                ) AS avg_dns_time

            FROM measurements

            WHERE timestamp >= ?
            """,
            (cutoff,)
        )

        stats_row = cursor.fetchone()

        total_checks = stats_row["total_checks"] or 0
        online_checks = stats_row["online_checks"] or 0

        if total_checks > 0:
            uptime_percentage = (
                online_checks / total_checks
            ) * 100
        else:
            uptime_percentage = 100.0

        # --------------------------------------------------------
        # Outage statistics
        # --------------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                start_time,
                end_time,
                duration_seconds,
                status

            FROM outages

            WHERE
                start_time >= ?
                OR (
                    status = 'ONGOING'
                    AND start_time < ?
                )

            ORDER BY start_time ASC
            """,
            (cutoff, cutoff)
        )

        outage_rows = cursor.fetchall()

        outage_count = len(outage_rows)

        total_downtime = 0
        longest_outage = 0

        for outage in outage_rows:
            start_time = datetime.fromisoformat(
                outage["start_time"]
            )

            if outage["status"] == "ONGOING":
                end_time = now
            elif outage["end_time"]:
                end_time = datetime.fromisoformat(
                    outage["end_time"]
                )
            else:
                end_time = now

            # Only count the part of an outage inside the
            # requested statistics window.
            effective_start = max(
                start_time,
                datetime.fromisoformat(cutoff)
            )

            duration = max(
                0,
                int(
                    (
                        end_time - effective_start
                    ).total_seconds()
                )
            )

            total_downtime += duration
            longest_outage = max(
                longest_outage,
                duration
            )

        return {
            "total_checks": total_checks,

            "uptime_percentage": round(
                uptime_percentage,
                2
            ),

            "avg_latency": round(
                stats_row["avg_latency"] or 0,
                2
            ),

            "min_latency": round(
                stats_row["min_latency"] or 0,
                2
            ),

            "max_latency": round(
                stats_row["max_latency"] or 0,
                2
            ),

            "avg_packet_loss": round(
                stats_row["avg_packet_loss"] or 0,
                2
            ),

            "avg_dns_time": round(
                stats_row["avg_dns_time"] or 0,
                2
            ),

            "outage_count": outage_count,

            "longest_outage_sec": longest_outage,

            "total_downtime_sec": total_downtime,
        }

    finally:
        conn.close()
