import platform
import re
import socket
import subprocess
import threading
import time
from datetime import datetime, timezone

import database


class NetworkMonitor(threading.Thread):

    def __init__(self):
        super().__init__(
            name="NetworkMonitor",
            daemon=True
        )

        self.running = True
        self.current_outage_id = None

        self.recent_ping_results = []

        self.window_size = 10

        self.session_start = datetime.now(timezone.utc)

    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------

    def stop(self):
        self.running = False

    # ------------------------------------------------------------
    # DNS
    # ------------------------------------------------------------

    def measure_dns(self, target_host):
        start = time.perf_counter()

        try:
            socket.getaddrinfo(
                target_host,
                None,
                type=socket.SOCK_STREAM
            )

            elapsed = (
                time.perf_counter() - start
            ) * 1000.0

            return round(elapsed, 2)

        except Exception:
            return None

    # ------------------------------------------------------------
    # Ping
    # ------------------------------------------------------------

    def measure_ping(self, target):
        system = platform.system().lower()

        if system == "windows":
            command = [
                "ping",
                "-n",
                "1",
                "-w",
                "1000",
                target
            ]
        else:
            command = [
                "ping",
                "-c",
                "1",
                "-W",
                "1",
                target
            ]

        start = time.perf_counter()

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=3
            )

            if result.returncode != 0:
                return None

            output = result.stdout

            # Handles examples such as:
            #
            # time=14ms
            # time=14.3 ms
            # time<1ms
            #
            match = re.search(
                r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms",
                output,
                re.IGNORECASE
            )

            if match:
                return round(
                    float(match.group(1)),
                    2
                )

            # Fallback if the OS output format differs.
            elapsed = (
                time.perf_counter() - start
            ) * 1000.0

            return round(elapsed, 2)

        except (
            subprocess.TimeoutExpired,
            subprocess.SubprocessError,
            OSError
        ):
            return None

    # ------------------------------------------------------------
    # TCP fallback
    # ------------------------------------------------------------

    def tcp_ping_fallback(self, target, port=80):
        start = time.perf_counter()

        try:
            with socket.create_connection(
                (target, port),
                timeout=1.5
            ):
                pass

            elapsed = (
                time.perf_counter() - start
            ) * 1000.0

            return round(elapsed, 2)

        except Exception:
            return None

    # ------------------------------------------------------------
    # Health score
    # ------------------------------------------------------------

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

        if dns_time is not None:

            if dns_time > 150:
                score -= 20

            elif dns_time > 75:
                score -= 10

        else:
            score -= 15

        return max(
            0,
            min(
                100,
                round(score)
            )
        )

    # ------------------------------------------------------------
    # Packet loss
    # ------------------------------------------------------------

    def calculate_packet_loss(self, ping_success):
        self.recent_ping_results.append(
            1 if ping_success else 0
        )

        if len(self.recent_ping_results) > self.window_size:
            self.recent_ping_results.pop(0)

        total = len(self.recent_ping_results)

        if total == 0:
            return 0.0

        failed = self.recent_ping_results.count(0)

        return round(
            (failed / total) * 100,
            2
        )

    # ------------------------------------------------------------
    # Main monitor loop
    # ------------------------------------------------------------

    def run(self):
        database.init_db()

        cleanup_counter = 0

        while self.running:

            try:
                settings = database.get_settings()

                interval = float(
                    settings.get(
                        "interval",
                        5
                    )
                )

                interval = max(
                    1,
                    min(
                        interval,
                        60
                    )
                )

                ping_target = settings.get(
                    "ping_target",
                    "8.8.8.8"
                )

                dns_target = settings.get(
                    "dns_target",
                    "one.one.one.one"
                )

                retention_days = int(
                    settings.get(
                        "retention_days",
                        7
                    )
                )

                # ------------------------------------------------
                # Network probes
                # ------------------------------------------------

                ping_time = self.measure_ping(
                    ping_target
                )

                # If normal ping fails, try TCP as a secondary
                # connectivity signal.
                tcp_time = None

                if ping_time is None:
                    tcp_time = self.tcp_ping_fallback(
                        ping_target
                    )

                dns_time = self.measure_dns(
                    dns_target
                )

                ping_success = (
                    ping_time is not None
                )

                # Connectivity is considered available when
                # either the configured ping target or DNS works.
                is_online = (
                    ping_success
                    or tcp_time is not None
                    or dns_time is not None
                )

                packet_loss = (
                    self.calculate_packet_loss(
                        ping_success
                    )
                )

                # Prefer real ICMP latency.
                latency = ping_time

                if latency is None and tcp_time is not None:
                    latency = tcp_time

                status = (
                    "ONLINE"
                    if is_online
                    else "OFFLINE"
                )

                # ------------------------------------------------
                # Outage tracking
                # ------------------------------------------------

                if is_online:

                    if self.current_outage_id is not None:

                        database.resolve_outage(
                            self.current_outage_id
                        )

                        self.current_outage_id = None

                else:

                    if self.current_outage_id is None:

                        self.current_outage_id = (
                            database.start_outage()
                        )

                # ------------------------------------------------
                # Store measurement
                # ------------------------------------------------

                database.insert_measurement(
                    status=status,
                    latency=latency,
                    packet_loss=packet_loss,
                    dns_time=dns_time
                )

                # ------------------------------------------------
                # Cleanup
                # ------------------------------------------------

                cleanup_counter += 1

                if cleanup_counter >= 100:

                    database.cleanup_old_data(
                        retention_days
                    )

                    cleanup_counter = 0

                # ------------------------------------------------
                # Interruptible-ish sleep
                # ------------------------------------------------

                for _ in range(
                    max(
                        1,
                        int(interval * 10)
                    )
                ):

                    if not self.running:
                        break

                    time.sleep(0.1)

            except Exception as error:

                print(
                    f"[NetworkMonitor] Error: {error}"
                )

                time.sleep(2)
