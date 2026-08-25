# Internet Black Box

> A local network monitoring dashboard that keeps track of what your internet connection is actually doing.

Internet Black Box is a lightweight network monitoring tool built with Python and Flask. It runs locally on your computer and continuously records connection status, latency, packet loss, DNS response time, and outages.

The goal is simple: instead of wondering whether your internet is unstable, you can actually see it.

---

## What it does

- Monitors your internet connection in the background
- Measures latency and DNS response time
- Tracks packet loss
- Detects and records outages
- Calculates a network health score
- Displays live telemetry through a web dashboard
- Keeps historical statistics
- Includes a manual HTTP bandwidth test
- Stores monitoring data locally using SQLite
- Works even when the monitored internet connection goes offline because the dashboard itself runs locally

---

## Dashboard

The dashboard is divided into a few simple sections:

### Dashboard

Shows the current state of your connection, including:

- Online / Offline status
- Network health score
- Current latency
- Packet loss
- DNS latency
- 24-hour reliability
- Live latency graph

### Statistics

View historical network performance for:

- Today
- Last 7 days
- Last 30 days

Statistics include uptime, outages, downtime, latency, packet loss, and DNS performance.

### Outages

Every detected outage is logged with:

- Start time
- Recovery time
- Duration
- Current status

### Speed Test

A manually triggered HTTP bandwidth test measures actual transferred data instead of relying on a tiny request.

The test reports:

- Download speed
- Upload speed
- Duration
- Amount of data transferred
- Test timestamp

Speed tests are only executed when manually started so they don't constantly consume bandwidth.

### Settings

Monitoring behavior can be adjusted from the dashboard.

Available settings include:

- Monitoring interval
- Ping target
- DNS target
- Database retention period
- Maximum graph points

---

## How it works

Internet Black Box has two main parts.

### Network monitor

A background Python thread periodically performs network checks.

It uses:

- ICMP ping when available
- TCP fallback when ICMP isn't available
- DNS resolution timing
- Rolling packet-loss calculations

The results are stored in SQLite.

When multiple checks fail, the system records an outage. Once connectivity returns, the outage is automatically closed and its duration is calculated.

### Web dashboard

Flask provides the local web interface and API.

The frontend periodically requests the latest data and updates the dashboard without requiring a page reload.

The interface is built using:

- HTML
- CSS
- Vanilla JavaScript
- Chart.js

---

## Project structure

```text
internet-black-box/
│
├── app.py
├── monitor.py
├── database.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── templates/
│   └── index.html
│
├── static/
│   ├── style.css
│   └── script.js
│
└── data/
    └── blackbox.db
