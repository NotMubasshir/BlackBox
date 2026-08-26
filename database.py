import os
import sqlite3

from datetime import (
    datetime,
    timedelta,
    timezone,
)


DB_DIR = os.path.join(
    os.path.dirname(__file__),
    "data"
)

DB_PATH = os.path.join(
    DB_DIR,
    "blackbox.db"
)


DEFAULT_SETTINGS = {
    "interval": "5",

    "ping_target":
        "1.1.1.1",

    "dns_target":
        "1.1.1.1",

    "dns_probe_domain":
        "example.com",

    "retention_days":
        "7",

    "max_graph_points":
        "40",

    "packet_loss_warning":
        "1.0",

    "packet_loss_poor":
        "5.0",
}


def get_connection():

    os.makedirs(
        DB_DIR,
        exist_ok=True
    )

    conn = sqlite3.connect(
        DB_PATH,
        timeout=10.0
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA journal_mode=WAL"
    )

    conn.execute(
        "PRAGMA busy_timeout=10000"
    )

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
        CREATE INDEX IF NOT EXISTS
        idx_measurements_timestamp
        ON measurements(timestamp)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_outages_start
        ON outages(start_time)
    """)

    for key, value in DEFAULT_SETTINGS.items():

        cursor.execute(
            """
            INSERT OR IGNORE INTO settings
            (key, value)
            VALUES (?, ?)
            """,
            (key, value)
        )

    # Upgrade older installations automatically.

    cursor.execute(
        """
        UPDATE settings
        SET value = ?
        WHERE key = ?
        AND value = ?
        """,
        (
            "1.1.1.1",
            "dns_target",
            "one.one.one.one"
        )
    )

    cursor.execute(
        """
        UPDATE settings
        SET value = ?
        WHERE key = ?
        AND value = ?
        """,
        (
            "1.1.1.1",
            "ping_target",
            "8.8.8.8"
        )
    )

    conn.commit()

    conn.close()


def get_settings():

    conn = get_connection()

    rows = conn.execute(
        "SELECT key, value FROM settings"
    ).fetchall()

    conn.close()

    settings = dict(
        DEFAULT_SETTINGS
    )

    settings.update({
        row["key"]:
            row["value"]
        for row in rows
    })

    return settings


def update_setting(
    key,
    value
):

    conn = get_connection()

    conn.execute(
        """
        INSERT OR REPLACE INTO settings
        (key, value)
        VALUES (?, ?)
        """,
        (
            key,
            str(value)
        )
    )

    conn.commit()

    conn.close()


def insert_measurement(
    status,
    latency,
    packet_loss,
    dns_time
):

    conn = get_connection()

    now = datetime.now(
        timezone.utc
    ).isoformat()

    conn.execute(
        """
        INSERT INTO measurements
        (
            timestamp,
            status,
            latency,
            packet_loss,
            dns_time
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            now,
            status,
            latency,
            packet_loss,
            dns_time
        )
    )

    conn.commit()

    conn.close()


def start_outage():

    conn = get_connection()

    existing = conn.execute(
        """
        SELECT id
        FROM outages
        WHERE status = "ONGOING"
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    if existing:

        conn.close()

        return existing["id"]

    now = datetime.now(
        timezone.utc
    ).isoformat()

    cursor = conn.execute(
        """
        INSERT INTO outages
        (
            start_time,
            status
        )
        VALUES (?, "ONGOING")
        """,
        (now,)
    )

    outage_id = cursor.lastrowid

    conn.commit()

    conn.close()

    return outage_id


def resolve_outage(
    outage_id
):

    conn = get_connection()

    row = conn.execute(
        """
        SELECT start_time
        FROM outages
        WHERE id = ?
        """,
        (outage_id,)
    ).fetchone()

    if row:

        start_time = datetime.fromisoformat(
            row["start_time"]
        )

        now = datetime.now(
            timezone.utc
        )

        duration = max(
            0,
            int(
                (
                    now - start_time
                ).total_seconds()
            )
        )

        conn.execute(
            """
            UPDATE outages
            SET
                end_time = ?,
                duration_seconds = ?,
                status = "RESOLVED"
            WHERE id = ?
            """,
            (
                now.isoformat(),
                duration,
                outage_id
            )
        )

        conn.commit()

    conn.close()


def cleanup_old_data(
    retention_days
):

    cutoff = (
        datetime.now(
            timezone.utc
        )
        -
        timedelta(
            days=int(
                retention_days
            )
        )
    ).isoformat()

    conn = get_connection()

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
        AND status = "RESOLVED"
        """,
        (cutoff,)
    )

    conn.commit()

    conn.close()


def get_latest_metrics(
    limit=40
):

    conn = get_connection()

    rows = conn.execute(
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
        (int(limit),)
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in reversed(rows)
    ]


def get_recent_outages(
    limit=20
):

    conn = get_connection()

    rows = conn.execute(
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
        (int(limit),)
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


def get_statistics(
    days=1
):

    cutoff = (
        datetime.now(
            timezone.utc
        )
        -
        timedelta(
            days=int(days)
        )
    ).isoformat()

    conn = get_connection()

    stats = conn.execute(
        """
        SELECT

            COUNT(*)
                AS total_checks,

            SUM(
                CASE
                    WHEN status = 'ONLINE'
                    THEN 1
                    ELSE 0
                END
            )
                AS online_checks,

            AVG(
                CASE
                    WHEN status = 'ONLINE'
                    THEN latency
                END
            )
                AS avg_latency,

            MIN(
                CASE
                    WHEN status = 'ONLINE'
                    THEN latency
                END
            )
                AS min_latency,

            MAX(
                CASE
                    WHEN status = 'ONLINE'
                    THEN latency
                END
            )
                AS max_latency,

            AVG(
                CASE
                    WHEN status = 'ONLINE'
                    THEN packet_loss
                END
            )
                AS avg_packet_loss,

            AVG(
                CASE
                    WHEN status = 'ONLINE'
                    THEN dns_time
                END
            )
                AS avg_dns_time

        FROM measurements

        WHERE timestamp >= ?
        """,
        (cutoff,)
    ).fetchone()

    outages = conn.execute(
        """
        SELECT

            COUNT(*)
                AS outage_count,

            MAX(
                COALESCE(
                    duration_seconds,
                    0
                )
            )
                AS max_duration,

            SUM(
                COALESCE(
                    duration_seconds,
                    0
                )
            )
                AS total_downtime

        FROM outages

        WHERE start_time >= ?
        """,
        (cutoff,)
    ).fetchone()

    conn.close()

    total_checks = (
        stats["total_checks"]
        or 0
    )

    online_checks = (
        stats["online_checks"]
        or 0
    )

    uptime = (
        online_checks
        /
        total_checks
        *
        100
    ) if total_checks else 100.0

    return {

        "total_checks":
            total_checks,

        "uptime_percentage":
            round(
                uptime,
                2
            ),

        "avg_latency":
            round(
                stats["avg_latency"]
                or 0,
                2
            ),

        "min_latency":
            round(
                stats["min_latency"]
                or 0,
                2
            ),

        "max_latency":
            round(
                stats["max_latency"]
                or 0,
                2
            ),

        "avg_packet_loss":
            round(
                stats["avg_packet_loss"]
                or 0,
                2
            ),

        "avg_dns_time":
            round(
                stats["avg_dns_time"]
                or 0,
                2
            ),

        "outage_count":
            outages["outage_count"]
            or 0,

        "longest_outage_sec":
            outages["max_duration"]
            or 0,

        "total_downtime_sec":
            outages["total_downtime"]
            or 0,
    }
