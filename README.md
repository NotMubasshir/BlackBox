# Internet Black Box

A local network monitor for keeping an eye on your internet connection.

Internet Black Box runs quietly in the background and records metrics like latency, packet loss, DNS response time, and connection outages. Everything is stored locally in SQLite, meaning there are no cloud services or external dashboards involved.

> **Every connection leaves a trace.**

---

## What It Does

* **Continuous Monitoring:** Keeps track of your internet connection status around the clock.
* **Latency Tracking:** Measures ping and response times.
* **Packet Loss Analysis:** Tracks packet drops during check cycles.
* **DNS Performance:** Measures DNS response time.
* **Outage Detection:** Detects and records connection drops and recovery times.
* **Visual Dashboards:** Displays live latency and DNS graphs alongside 1-day, 7-day, and 30-day historical statistics.
* **Health Scoring:** Calculates an overall network health score.
* **Local Storage:** Stores all data securely in a local SQLite database.

---

## How It Works

The application is split into two primary components:

1. **Background Monitor (`monitor.py`):** Runs a background thread that periodically checks the configured ping target, performs a DNS lookup, assesses connectivity, calculates packet loss, and writes the results to SQLite. It also manages outage start and end records.
2. **Local Dashboard (`app.py`):** Runs a lightweight Flask server that exposes the recorded data via a REST API, powering a responsive frontend dashboard that updates dynamically.

### Data Flow

```text
Internet
   │
   ▼
Network Monitor (Ping / DNS / Connectivity)
   │
   ▼
SQLite Database
   │
   ▼
Flask API
   │
   ▼
Browser Dashboard
Project StructurePlaintextinternet-black-box/
│
├── app.py
├── monitor.py
├── database.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── data/
│   └── blackbox.db
│
├── templates/
│   └── index.html
│
└── static/
    ├── style.css
    └── script.js
(Note: The database directory and file are created automatically if they do not already exist.)Tech StackBackendPythonFlaskSQLite3socket, subprocess, threadingFrontendHTML5CSS3Vanilla JavaScriptChart.js (No heavy frontend frameworks required)InstallationRequirementsPython 3.8+Windows, Linux, or macOSAn internet connection for initial package setupStepsClone the repository:Bashgit clone [https://github.com/NotMubasshir/internet-black-box.git](https://github.com/NotMubasshir/internet-black-box.git)
cd internet-black-box
Install dependencies:Bashpip install -r requirements.txt
Start the application:Bashpython app.py
Access the dashboard:Open your browser and navigate to:http://127.0.0.1:5000ConfigurationSettings can be managed directly from the web dashboard interface.SettingDescriptionDefault ValueMonitoring IntervalHow often the monitor performs a check5 secondsPing TargetHost or IP address used for latency testing8.8.8.8DNS TargetDomain used for DNS lookup testingone.one.one.oneData RetentionHow long historical records are kept7 daysGraph PointsNumber of recent measurements displayed on live graphs30Database SchemaInternet Black Box utilizes a local SQLite database located at data/blackbox.db. It stores two main types of logs:Measurements: Timestamps, connection status, latency values, packet loss percentages, and DNS response times for each monitoring cycle.Outages: Start times, end times, total duration, and status for every detected network drop.Speed TestThe dashboard includes an optional manual download speed test feature. Unlike background monitoring checks, the speed test actively transfers data and is intended for manual, occasional troubleshooting rather than continuous automated tracking.Why I Built ThisMost internet connectivity issues are intermittent. A connection might look fine during a quick manual check, but that does not explain performance drops from an hour ago.Internet Black Box answers questions such as:Did my internet connection actually go down?How long did the outage last?Was my latency unusually high at a specific time?Has packet loss been happening repeatedly?How reliable has my connection been over the last week?PrivacyThis project is built with a local-first philosophy.No user accountsNo cloud databasesNo telemetry or tracking servicesNo external dashboardsAll network metrics remain securely on your machine.LicenseThis project is open-source. Refer to the repository's license file for details.AuthorMubasshir HossainGitHub: NotMubasshirIf you find a bug or have suggestions for improvement, feel free to open an issue or submit a pull request.
