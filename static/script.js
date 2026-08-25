document.addEventListener("DOMContentLoaded", () => {
    let latencyChart = null;
    let selectedStatsDays = 1;
    let dashboardTimer = null;
    let isDashboardUpdating = false;

    // ------------------------------------------------------------
    // DOM helpers
    // ------------------------------------------------------------

    const $ = (id) => document.getElementById(id);

    function setText(id, value) {
        const element = $(id);
        if (element) {
            element.textContent = value;
        }
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // ------------------------------------------------------------
    // Navigation
    // ------------------------------------------------------------

    const navItems = document.querySelectorAll(".nav-item");
    const viewSections = document.querySelectorAll(".view-section");

    navItems.forEach((item) => {
        item.addEventListener("click", () => {
            const target = item.dataset.target;
            const targetSection = $(target);

            if (!targetSection) return;

            navItems.forEach((nav) => nav.classList.remove("active"));
            viewSections.forEach((view) => view.classList.remove("active"));

            item.classList.add("active");
            targetSection.classList.add("active");

            if (target === "view-statistics") {
                fetchStatistics(selectedStatsDays);
            }

            if (target === "view-outages") {
                fetchOutages();
            }

            if (target === "view-settings") {
                loadSettings();
            }
        });
    });

    // ------------------------------------------------------------
    // Formatting
    // ------------------------------------------------------------

    function formatTime(isoString) {
        if (!isoString) return "--:--:--";

        const date = new Date(isoString);

        if (Number.isNaN(date.getTime())) {
            return "--:--:--";
        }

        return date.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
        });
    }

    function formatDateTime(isoString) {
        if (!isoString) return "Unknown";

        const date = new Date(isoString);

        if (Number.isNaN(date.getTime())) {
            return "Unknown";
        }

        return date.toLocaleString([], {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
        });
    }

    function formatDuration(seconds) {
        if (seconds === null || seconds === undefined) {
            return "Ongoing";
        }

        seconds = Math.max(0, Math.floor(Number(seconds)));

        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;

        if (days > 0) {
            return `${days}d ${hours}h ${minutes}m`;
        }

        if (hours > 0) {
            return `${hours}h ${minutes}m ${secs}s`;
        }

        if (minutes > 0) {
            return `${minutes}m ${secs}s`;
        }

        return `${secs}s`;
    }

    function formatSessionUptime(totalSeconds) {
        totalSeconds = Math.max(0, Math.floor(Number(totalSeconds) || 0));

        const days = Math.floor(totalSeconds / 86400);
        const hours = Math.floor((totalSeconds % 86400) / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;

        if (days > 0) {
            return `${days}d ${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
        }

        return [
            String(hours).padStart(2, "0"),
            String(minutes).padStart(2, "0"),
            String(seconds).padStart(2, "0")
        ].join(":");
    }

    function formatNumber(value, decimals = 2) {
        if (value === null || value === undefined || Number.isNaN(Number(value))) {
            return "--";
        }

        return Number(value).toFixed(decimals);
    }

    // ------------------------------------------------------------
    // API helper
    // ------------------------------------------------------------

    async function apiFetch(url, options = {}) {
        const response = await fetch(url, {
            cache: "no-store",
            ...options
        });

        let data;

        try {
            data = await response.json();
        } catch {
            throw new Error(`Server returned HTTP ${response.status}`);
        }

        if (!response.ok) {
            throw new Error(data.message || `Request failed (${response.status})`);
        }

        return data;
    }

    // ------------------------------------------------------------
    // Chart
    // ------------------------------------------------------------

    function initChart() {
        const canvas = $("liveLatencyChart");

        if (!canvas || typeof Chart === "undefined") {
            console.error("Chart.js is unavailable.");
            return;
        }

        const ctx = canvas.getContext("2d");

        latencyChart = new Chart(ctx, {
            type: "line",

            data: {
                labels: [],

                datasets: [
                    {
                        label: "Ping",
                        data: [],
                        borderColor: "#22d3ee",
                        backgroundColor: "rgba(34, 211, 238, 0.08)",
                        borderWidth: 2,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        tension: 0.35,
                        fill: true,
                        spanGaps: true
                    },
                    {
                        label: "DNS",
                        data: [],
                        borderColor: "#60a5fa",
                        backgroundColor: "transparent",
                        borderWidth: 1.5,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        borderDash: [5, 5],
                        tension: 0.35,
                        fill: false,
                        spanGaps: true
                    }
                ]
            },

            options: {
                responsive: true,
                maintainAspectRatio: false,

                interaction: {
                    intersect: false,
                    mode: "index"
                },

                animation: false,

                scales: {
                    x: {
                        grid: {
                            color: "rgba(148, 163, 184, 0.07)"
                        },
                        border: {
                            display: false
                        },
                        ticks: {
                            color: "#64748b",
                            maxTicksLimit: 8,
                            font: {
                                family: "Inter, system-ui, sans-serif",
                                size: 10
                            }
                        }
                    },

                    y: {
                        beginAtZero: true,

                        grid: {
                            color: "rgba(148, 163, 184, 0.07)"
                        },

                        border: {
                            display: false
                        },

                        ticks: {
                            color: "#64748b",
                            font: {
                                family: "Inter, system-ui, sans-serif",
                                size: 10
                            },

                            callback: (value) => `${value} ms`
                        }
                    }
                },

                plugins: {
                    legend: {
                        position: "top",
                        align: "start",

                        labels: {
                            color: "#94a3b8",
                            usePointStyle: true,
                            pointStyle: "line",
                            boxWidth: 28,
                            padding: 18
                        }
                    },

                    tooltip: {
                        backgroundColor: "#111827",
                        borderColor: "rgba(148, 163, 184, 0.15)",
                        borderWidth: 1,
                        titleColor: "#f8fafc",
                        bodyColor: "#cbd5e1",
                        padding: 12,

                        callbacks: {
                            label: (context) => {
                                const value = context.raw;

                                if (value === null || value === undefined) {
                                    return `${context.dataset.label}: unavailable`;
                                }

                                return `${context.dataset.label}: ${value} ms`;
                            }
                        }
                    }
                }
            }
        });
    }

    function updateChart(metrics) {
        if (!latencyChart) return;

        latencyChart.data.labels = metrics.map((metric) =>
            formatTime(metric.timestamp)
        );

        latencyChart.data.datasets[0].data = metrics.map((metric) =>
            metric.latency === null ? null : metric.latency
        );

        latencyChart.data.datasets[1].data = metrics.map((metric) =>
            metric.dns_time === null ? null : metric.dns_time
        );

        latencyChart.update("none");
    }

    // ------------------------------------------------------------
    // Dashboard
    // ------------------------------------------------------------

    async function updateDashboard() {
        if (isDashboardUpdating) return;

        isDashboardUpdating = true;

        try {
            const [statusData, metricsData] = await Promise.all([
                apiFetch("/api/status"),
                apiFetch("/api/metrics")
            ]);

            const beacon = $("status-beacon");
            const statusTitle = $("status-title");
            const statusSubtitle = $("status-subtitle");

            const isOnline = statusData.status === "ONLINE";

            if (beacon) {
                beacon.className = `beacon ${isOnline ? "online" : "offline"}`;
            }

            setText(
                "status-title",
                isOnline ? "Online" : "Connection unavailable"
            );

            setText(
                "status-subtitle",
                isOnline
                    ? "Your internet connection is operating normally."
                    : "Network probes are currently failing."
            );

            setText("health-score-val", statusData.health_score);
            setText(
                "session-uptime-text",
                formatSessionUptime(statusData.session_duration_seconds)
            );

            setText(
                "card-reliability-val",
                `${formatNumber(statusData.reliability_today)}%`
            );

            // Ping
            const pingElement = $("card-ping-val");
            const pingBadge = $("card-ping-badge");

            if (statusData.latency !== null) {
                setText(
                    "card-ping-val",
                    `${formatNumber(statusData.latency)} ms`
                );

                if (statusData.latency < 40) {
                    pingBadge.textContent = "Excellent";
                    pingBadge.className = "badge excellent";
                } else if (statusData.latency < 90) {
                    pingBadge.textContent = "Good";
                    pingBadge.className = "badge good";
                } else if (statusData.latency < 180) {
                    pingBadge.textContent = "Elevated";
                    pingBadge.className = "badge warning";
                } else {
                    pingBadge.textContent = "High";
                    pingBadge.className = "badge critical";
                }
            } else {
                pingElement.textContent = "Unavailable";
                pingBadge.textContent = "Offline";
                pingBadge.className = "badge critical";
            }

            // Packet loss
            const packetLoss = statusData.packet_loss;

            if (packetLoss !== null) {
                setText(
                    "card-loss-val",
                    `${formatNumber(packetLoss)}%`
                );

                if (packetLoss === 0) {
                    $("card-loss-badge").textContent = "None";
                    $("card-loss-badge").className = "badge excellent";
                } else if (packetLoss <= 1) {
                    $("card-loss-badge").textContent = "Low";
                    $("card-loss-badge").className = "badge good";
                } else if (packetLoss <= 5) {
                    $("card-loss-badge").textContent = "Warning";
                    $("card-loss-badge").className = "badge warning";
                } else {
                    $("card-loss-badge").textContent = "High";
                    $("card-loss-badge").className = "badge critical";
                }
            } else {
                setText("card-loss-val", "--");
                $("card-loss-badge").textContent = "--";
                $("card-loss-badge").className = "badge";
            }

            // DNS
            const dnsTime = statusData.dns_time;

            if (dnsTime !== null) {
                setText(
                    "card-dns-val",
                    `${formatNumber(dnsTime)} ms`
                );

                if (dnsTime < 50) {
                    $("card-dns-badge").textContent = "Fast";
                    $("card-dns-badge").className = "badge excellent";
                } else if (dnsTime < 100) {
                    $("card-dns-badge").textContent = "Good";
                    $("card-dns-badge").className = "badge good";
                } else if (dnsTime < 200) {
                    $("card-dns-badge").textContent = "Slow";
                    $("card-dns-badge").className = "badge warning";
                } else {
                    $("card-dns-badge").textContent = "Very slow";
                    $("card-dns-badge").className = "badge critical";
                }
            } else {
                setText("card-dns-val", "Failed");
                $("card-dns-badge").textContent = "Failed";
                $("card-dns-badge").className = "badge critical";
            }

            updateChart(metricsData);
        } catch (error) {
            console.error("Dashboard update failed:", error);

            const beacon = $("status-beacon");

            if (beacon) {
                beacon.className = "beacon offline";
            }

            setText("status-title", "Monitor unavailable");
            setText(
                "status-subtitle",
                "Unable to communicate with the local monitoring service."
            );
        } finally {
            isDashboardUpdating = false;
        }
    }

    // ------------------------------------------------------------
    // Statistics
    // ------------------------------------------------------------

    const tabBtns = document.querySelectorAll(".btn-tab");

    tabBtns.forEach((button) => {
        button.addEventListener("click", () => {
            tabBtns.forEach((btn) => btn.classList.remove("active"));

            button.classList.add("active");

            selectedStatsDays = Number(button.dataset.days) || 1;

            fetchStatistics(selectedStatsDays);
        });
    });

    async function fetchStatistics(days) {
        try {
            const data = await apiFetch(`/api/statistics?days=${days}`);

            setText("stats-uptime", `${formatNumber(data.uptime_percentage)}%`);
            setText("stats-outages-count", data.outage_count);
            setText(
                "stats-downtime",
                formatDuration(data.total_downtime_sec)
            );
            setText(
                "stats-longest-outage",
                formatDuration(data.longest_outage_sec)
            );

            setText(
                "stats-avg-ping",
                `${formatNumber(data.avg_latency)} ms`
            );

            setText(
                "stats-min-max-ping",
                `${formatNumber(data.min_latency)} / ${formatNumber(data.max_latency)} ms`
            );

            setText(
                "stats-avg-loss",
                `${formatNumber(data.avg_packet_loss)}%`
            );

            setText(
                "stats-avg-dns",
                `${formatNumber(data.avg_dns_time)} ms`
            );
        } catch (error) {
            console.error("Statistics error:", error);
        }
    }

    // ------------------------------------------------------------
    // Outages
    // ------------------------------------------------------------

    async function fetchOutages() {
        const container = $("outages-timeline-list");

        if (!container) return;

        try {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="loading-spinner"></div>
                    <p>Loading outage history...</p>
                </div>
            `;

            const outages = await apiFetch("/api/outages");

            if (!Array.isArray(outages) || outages.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">✓</div>
                        <h4>No outages recorded</h4>
                        <p>Your monitor has not detected any connection outages.</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = outages.map((outage) => {
                const resolved = outage.status === "RESOLVED";

                return `
                    <div class="timeline-item ${resolved ? "resolved" : "ongoing"}">
                        <div class="timeline-marker"></div>

                        <div class="timeline-content">
                            <div class="timeline-top">
                                <span class="timeline-status ${resolved ? "resolved" : "ongoing"}">
                                    ${resolved ? "Resolved" : "Ongoing"}
                                </span>

                                <span class="timeline-duration">
                                    ${escapeHtml(formatDuration(outage.duration_seconds))}
                                </span>
                            </div>

                            <div class="timeline-time">
                                ${escapeHtml(formatDateTime(outage.start_time))}
                                ${outage.end_time
                                    ? ` → ${escapeHtml(formatDateTime(outage.end_time))}`
                                    : ""
                                }
                            </div>
                        </div>
                    </div>
                `;
            }).join("");
        } catch (error) {
            console.error("Outage error:", error);

            container.innerHTML = `
                <div class="empty-state error-state">
                    <div class="empty-icon">!</div>
                    <h4>Unable to load outages</h4>
                    <p>${escapeHtml(error.message)}</p>
                </div>
            `;
        }
    }

    // ------------------------------------------------------------
    // Speed test
    // ------------------------------------------------------------

    const speedTestButton = $("btn-start-speedtest");

    if (speedTestButton) {
        speedTestButton.addEventListener("click", async () => {
            speedTestButton.disabled = true;
            speedTestButton.textContent = "Testing…";

            setText("speed-val", "—");
            setText("speed-duration", "Running");
            setText("speed-bytes", "Downloading…");
            setText("speed-time", "Now");

            try {
                const data = await apiFetch("/api/speedtest", {
                    method: "POST"
                });

                if (data.status !== "success") {
                    throw new Error(data.message || "Speed test failed.");
                }

                setText(
                    "speed-val",
                    Number(data.download_speed_mbps).toFixed(2)
                );

                setText(
                    "speed-duration",
                    `${data.duration_seconds}s`
                );

                setText(
                    "speed-bytes",
                    formatBytes(data.bytes_received)
                );

                setText(
                    "speed-time",
                    formatDateTime(data.timestamp)
                );
            } catch (error) {
                console.error("Speed test error:", error);

                setText("speed-val", "—");
                setText("speed-duration", "Failed");
                setText("speed-bytes", "—");
                setText("speed-time", "—");

                showToast(error.message, "error");
            } finally {
                speedTestButton.disabled = false;
                speedTestButton.textContent = "Run speed test";
            }
        });
    }

    function formatBytes(bytes) {
        bytes = Number(bytes) || 0;

        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) {
            return `${(bytes / 1024).toFixed(1)} KB`;
        }

        if (bytes < 1024 * 1024 * 1024) {
            return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
        }

        return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
    }

    // ------------------------------------------------------------
    // Settings
    // ------------------------------------------------------------

    async function loadSettings() {
        try {
            const data = await apiFetch("/api/settings");

            $("setting-interval").value = data.interval;
            $("setting-ping-target").value = data.ping_target;
            $("setting-dns-target").value = data.dns_target;
            $("setting-retention").value = data.retention_days;
            $("setting-graph-points").value = data.max_graph_points;
        } catch (error) {
            console.error("Settings loading error:", error);
        }
    }

    const settingsForm = $("settings-form");

    if (settingsForm) {
        settingsForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            const button = settingsForm.querySelector("button[type='submit']");
            const status = $("settings-save-status");

            const payload = {
                interval: $("setting-interval").value,
                ping_target: $("setting-ping-target").value.trim(),
                dns_target: $("setting-dns-target").value.trim(),
                retention_days: $("setting-retention").value,
                max_graph_points: $("setting-graph-points").value
            };

            button.disabled = true;
            button.textContent = "Saving…";

            try {
                await apiFetch("/api/settings", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(payload)
                });

                status.textContent = "Settings saved";
                status.className = "status-msg success";

                setTimeout(() => {
                    status.textContent = "";
                }, 3000);

                updateDashboard();
            } catch (error) {
                console.error("Settings save error:", error);

                status.textContent = error.message;
                status.className = "status-msg error";
            } finally {
                button.disabled = false;
                button.textContent = "Save settings";
            }
        });
    }

    // ------------------------------------------------------------
    // Toast
    // ------------------------------------------------------------

    function showToast(message, type = "info") {
        let toast = $("app-toast");

        if (!toast) {
            toast = document.createElement("div");
            toast.id = "app-toast";
            document.body.appendChild(toast);
        }

        toast.className = `toast ${type}`;
        toast.textContent = message;

        requestAnimationFrame(() => {
            toast.classList.add("visible");
        });

        setTimeout(() => {
            toast.classList.remove("visible");
        }, 3500);
    }

    // ------------------------------------------------------------
    // Init
    // ------------------------------------------------------------

    initChart();
    updateDashboard();

    dashboardTimer = setInterval(updateDashboard, 3000);

    window.addEventListener("beforeunload", () => {
        if (dashboardTimer) {
            clearInterval(dashboardTimer);
        }
    });
});
