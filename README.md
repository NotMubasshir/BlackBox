# Internet Black Box ⬛📶

> *"Every connection leaves a trace."*

**Internet Black Box** is a lightweight, local network-monitoring dashboard built with Python, Flask, SQLite, and vanilla JS. It runs locally on your machine, continuously tracking internet connectivity, latency, packet loss, and DNS resolution time while automatically logging internet outages into a local SQLite database.

---

## Features

- **Continuous Background Monitoring**: Checks connectivity, latency, packet loss, and DNS resolution.
- **Outage Detection**: Records exact start time, recovery time, and total downtime for every connection failure.
- **Network Health Score (0–100)**: Real-time calculated status score based on latency, packet loss, DNS resolution, and uptime.
- **Offline Resilient UI**: The Flask dashboard runs entirely locally and remains accessible even when your internet connection is completely offline.
- **Low Resource Usage**: Minimal CPU, RAM, and bandwidth consumption. Uses lightweight socket and system probes.
- **Historical Telemetry & Statistics**: View metrics aggregated for Today, 7 Days, or 30 Days.
- **Configurable**: Easily modify monitoring intervals, ping targets, DNS lookup targets, and data retention windows.

---

## Technical Architecture

+-------------------------------------------------------------+
|                     Internet Black Box                      |
+-------------------------------------------------------------+
|
+-----------------------+-----------------------+
|                                               |
v                                               v
+---------------+                             +------------------+
| Network       |                             | Flask Web Server |
| Monitor Thread|                             | (app.py)         |
+---------------+                             +------------------+
|                                               |
|  1. Ping / Socket Probes                      |  3. REST API
|  2. Outage & Metric Logging                   |     Endpoints
v                                               v
+---------------+                             +------------------+
| Local SQLite  | <-------------------------- | Vanilla JS UI    |
| (blackbox.db) |    4. Reads Metrics &       | (Chart.js)       |
+---------------+       Historical Data       +------------------+


---

## Tech Stack

- **Backend**: Python 3, Flask, SQLite3, Standard Socket & Subprocess Libraries
- **Frontend**: HTML5, Cyberpunk NOC CSS, Vanilla JavaScript, Chart.js (CDN)
- **Database**: SQLite3 (`data/blackbox.db`)

---

## Quick Start / Installation

### 1. Prerequisites
Ensure you have Python 3.8+ installed.

### 2. Setup Project
```bash
# Clone the repository
git clone <repository-url>
cd internet-black-box

# Install minimal dependencies
pip install -r requirements.txt