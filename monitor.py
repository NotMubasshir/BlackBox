import socket
import subprocess
import time
import platform
import threading
from datetime import datetime, timezone
import database

class NetworkMonitor(threading.Thread):
    def __init__ (self):
        super().__init__()
        self.daemon = True
        self.running = True
        self.current_outage_id = None
        self.recent_checks = []
        self.window_size = 10
        self.session_start = datetime.now(timezone.utc)

    def stop(self):
        self.running = False

    def measure_dns(self, target_host):
        start = time.perf_counter()
        try:
            socket.gethostbyname(target_host)
            elapsed = (time.perf_counter() - start) * 1000.0
            return round(elapsed, 2)
        except Exception:
            return None

    def measure_ping(self, target_ip):
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
        timeout_val = '1000' if platform.system().lower() == 'windows' else '1'
        
        cmd = ['ping', param, '1', timeout_param, timeout_val, target_ip]
        start = time.perf_counter()
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True)
            elapsed = (time.perf_counter() - start) * 1000.0

            if platform.system().lower() == 'windows':
                if "time=" in output:
                    time_str = output.split("time=")[1].split("ms")[0].strip()
                    time_str = time_str.replace("<", "")
                    return float(time_str)
                elif "Average =" in output:
                    time_str = output.split("Average =")[1].split("ms")[0].strip()
                    return float(time_str)
            else:
                if "time=" in output:
                    time_str = output.split("time=")[1].split(" ")[0]
                    return float(time_str)
            return round(elapsed, 2)
        except Exception:
            return self.tcp_ping_fallback(target_ip)

    def tcp_ping_fallback(self, target_ip, port=80):
        start = time.perf_counter()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            sock.connect((target_ip, port))
            sock.close()
            return round((time.perf_counter() - start) * 1000.0, 2)
        except Exception:
            return None

    def calculate_health_score(self, latency, packet_loss, dns_time, is_online):
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

        if packet_loss > 5.0:
            score -= 40
        elif packet_loss > 1.0:
            score -= 20

        if dns_time is not None:
            if dns_time > 150:
                score -= 20
            elif dns_time > 75:
                score -= 10
        elif is_online:
            score -= 15

        return max(0, min(100, round(score)))

    def run(self):
        database.init_db()
        cleanup_counter = 0

        while self.running:
            settings = database.get_settings()
            interval = float(settings.get('interval', 5))
            ping_target = settings.get('ping_target', '8.8.8.8')
            dns_target = settings.get('dns_target', 'one.one.one.one')
            retention_days = int(settings.get('retention_days', 7))

            dns_time = self.measure_dns(dns_target)
            ping_time = self.measure_ping(ping_target)

            is_success = (ping_time is not None) or (dns_time is not None)

            self.recent_checks.append(1 if is_success else 0)
            if len(self.recent_checks) > self.window_size:
                self.recent_checks.pop(0)

            failed_checks = self.recent_checks.count(0)
            packet_loss = round((failed_checks / len(self.recent_checks)) * 100.0, 2)

            if is_success:
                status = "ONLINE"
                if self.current_outage_id is not None:
                    database.resolve_outage(self.current_outage_id)
                    self.current_outage_id = None
            else:
                status = "OFFLINE"
                if self.current_outage_id is None:
                    self.current_outage_id = database.start_outage()

            database.insert_measurement(
                status=status,
                latency=ping_time,
                packet_loss=packet_loss,
                dns_time=dns_time
            )

            cleanup_counter += 1
            if cleanup_counter >= 100:
                database.cleanup_old_data(retention_days)
                cleanup_counter = 0

            time.sleep(interval)