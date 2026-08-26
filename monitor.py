import platform
import re
import socket
import struct
import threading
import time

from datetime import datetime, timezone

import subprocess

import database


class NetworkMonitor(threading.Thread):

    def __init__(self):

        super().__init__(
            daemon=True
        )

        self.running = True

        self.current_outage_id = None

        self.recent_checks = []

        self.window_size = 10

        self.session_start = (
            datetime.now(
                timezone.utc
            )
        )

    def stop(self):

        self.running = False

    def measure_ping(
        self,
        target
    ):

        system = platform.system().lower()

        if system == "windows":

            cmd = [
                "ping",
                "-n",
                "1",
                "-w",
                "1000",
                target
            ]

        else:

            cmd = [
                "ping",
                "-c",
                "1",
                "-W",
                "1",
                target
            ]

        start = time.perf_counter()

        try:

            output = subprocess.check_output(
                cmd,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=2.5,
                errors="ignore",
            )

            text = output.lower()

            match = re.search(
                r"time[=<]\s*"
                r"([0-9]+(?:\.[0-9]+)?)"
                r"\s*ms",
                text
            )

            if match:

                return round(
                    float(
                        match.group(1)
                    ),
                    2
                )

            match = re.search(
                r"average[ =]+"
                r"([0-9]+(?:\.[0-9]+)?)"
                r"\s*ms",
                text
            )

            if match:

                return round(
                    float(
                        match.group(1)
                    ),
                    2
                )

            return round(
                (
                    time.perf_counter()
                    -
                    start
                ) * 1000,
                2
            )

        except Exception:

            return self.tcp_ping_fallback(
                target
            )

    def tcp_ping_fallback(
        self,
        target,
        port=443
    ):

        start = time.perf_counter()

        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        sock.settimeout(1.5)

        try:

            sock.connect(
                (
                    target,
                    port
                )
            )

            return round(
                (
                    time.perf_counter()
                    -
                    start
                ) * 1000,
                2
            )

        except Exception:

            return None

        finally:

            sock.close()

    def measure_dns(
        self,
        dns_server,
        domain
    ):

        """
        Perform an actual DNS A-record query
        against the selected DNS server.
        """

        try:

            server = socket.gethostbyname(
                dns_server
            )

        except OSError:

            return None

        transaction_id = (
            int(
                time.time() * 1000
            )
            &
            0xFFFF
        )

        header = struct.pack(
            "!HHHHHH",
            transaction_id,
            0x0100,
            1,
            0,
            0,
            0
        )

        question = b""

        for label in domain.rstrip(".").split("."):

            encoded = label.encode(
                "idna"
            )

            if len(encoded) > 63:
                return None

            question += (
                bytes(
                    [len(encoded)]
                )
                +
                encoded
            )

        question += (
            b"\x00"
            +
            struct.pack(
                "!HH",
                1,
                1
            )
        )

        packet = (
            header
            +
            question
        )

        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        sock.settimeout(2.0)

        start = time.perf_counter()

        try:

            sock.sendto(
                packet,
                (
                    server,
                    53
                )
            )

            response, _ = sock.recvfrom(
                2048
            )

            if len(response) < 12:
                return None

            returned_id = struct.unpack(
                "!H",
                response[:2]
            )[0]

            flags = struct.unpack(
                "!H",
                response[2:4]
            )[0]

            answers = struct.unpack(
                "!H",
                response[6:8]
            )[0]

            if (
                returned_id != transaction_id
                or not (flags & 0x8000)
                or answers == 0
            ):
                return None

            return round(
                (
                    time.perf_counter()
                    -
                    start
                ) * 1000,
                2
            )

        except Exception:

            return None

        finally:

            sock.close()

    def calculate_health_score(
        self,
        latency,
        packet_loss,
        dns_time,
        is_online
    ):

        if not is_online:
            return 0

        score = 100.0

        if latency is not None:

            if latency > 200:
                score -= 30

            elif latency > 100:
                score -= 15

            elif latency > 50:
                score -= 5

        if packet_loss > 5:
            score -= 40

        elif packet_loss > 1:
            score -= 20

        if dns_time is None:

            score -= 15

        elif dns_time > 150:

            score -= 20

        elif dns_time > 75:

            score -= 10

        return max(
            0,
            min(
                100,
                round(score)
            )
        )

    def run(self):

        database.init_db()

        cleanup_counter = 0

        while self.running:

            settings = database.get_settings()

            interval = max(
                1.0,
                min(
                    float(
                        settings.get(
                            "interval",
                            5
                        )
                    ),
                    60.0
                )
            )

            ping_target = settings.get(
                "ping_target",
                "1.1.1.1"
            )

            dns_server = settings.get(
                "dns_target",
                "1.1.1.1"
            )

            dns_domain = settings.get(
                "dns_probe_domain",
                "example.com"
            )

            retention_days = int(
                settings.get(
                    "retention_days",
                    7
                )
            )

            ping_time = self.measure_ping(
                ping_target
            )

            dns_time = self.measure_dns(
                dns_server,
                dns_domain
            )

            # Either independent probe being successful
            # means the connection is reachable.

            is_success = (
                ping_time is not None
                or
                dns_time is not None
            )

            self.recent_checks.append(
                1 if is_success else 0
            )

            if len(
                self.recent_checks
            ) > self.window_size:

                self.recent_checks.pop(0)

            packet_loss = round(
                (
                    self.recent_checks.count(0)
                    /
                    len(self.recent_checks)
                )
                *
                100,
                2
            )

            if is_success:

                status = "ONLINE"

                if (
                    self.current_outage_id
                    is not None
                ):

                    database.resolve_outage(
                        self.current_outage_id
                    )

                    self.current_outage_id = None

            else:

                status = "OFFLINE"

                if (
                    self.current_outage_id
                    is None
                ):

                    self.current_outage_id = (
                        database.start_outage()
                    )

            database.insert_measurement(
                status=status,
                latency=ping_time,
                packet_loss=packet_loss,
                dns_time=dns_time
            )

            cleanup_counter += 1

            if cleanup_counter >= 100:

                database.cleanup_old_data(
                    retention_days
                )

                cleanup_counter = 0

            for _ in range(
                max(
                    1,
                    int(interval * 10)
                )
            ):

                if not self.running:
                    break

                time.sleep(0.1)
