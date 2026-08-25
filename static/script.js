document.addEventListener('DOMContentLoaded', () => {
    let latencyChart = null;
    let selectedStatsDays = 1;

    // View Navigation
    const navItems = document.querySelectorAll('.nav-item');
    const viewSections = document.querySelectorAll('.view-section');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const target = item.getAttribute('data-target');
            navItems.forEach(n => n.classList.remove('active'));
            viewSections.forEach(v => v.classList.remove('active'));

            item.classList.add('active');
            document.getElementById(target).classList.add('active');

            if (target === 'view-statistics') {
                fetchStatistics(selectedStatsDays);
            } else if (target === 'view-outages') {
                fetchOutages();
            } else if (target === 'view-settings') {
                loadSettings();
            }
        });
    });

    // Chart Initialization
    function initChart() {
        const ctx = document.getElementById('liveLatencyChart').getContext('2d');
        latencyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Ping (ms)',
                        borderColor: '#00f0ff',
                        backgroundColor: 'rgba(0, 240, 255, 0.1)',
                        data: [],
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: 'DNS Latency (ms)',
                        borderColor: '#3b82f6',
                        backgroundColor: 'transparent',
                        data: [],
                        borderWidth: 1.5,
                        borderDash: [4, 4],
                        tension: 0.3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#9ca3af', font: { family: 'monospace', size: 10 } }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#9ca3af', font: { family: 'monospace', size: 10 } }
                    }
                },
                plugins: {
                    legend: { labels: { color: '#f3f4f6', font: { size: 12 } } }
                }
            }
        });
    }

    // Helper Functions
    function formatTime(isoString) {
        if (!isoString) return '--:--:--';
        const d = new Date(isoString);
        return d.toLocaleTimeString();
    }

    function formatDuration(seconds) {
        if (!seconds && seconds !== 0) return 'Ongoing';
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        if (mins === 0) return `${secs}s`;
        return `${mins}m ${secs}s`;
    }

    function formatSessionUptime(totalSeconds) {
        const hrs = Math.floor(totalSeconds / 3600);
        const mins = Math.floor((totalSeconds % 3600) / 60);
        const secs = totalSeconds % 60;
        return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }

    // Fetch Status & Live Metrics
    async function updateDashboard() {
        try {
            const statusRes = await fetch('/api/status');
            const statusData = await statusRes.json();

            // Update top bar status
            const beacon = document.getElementById('status-beacon');
            const title = document.getElementById('status-title');
            const subtitle = document.getElementById('status-subtitle');

            if (statusData.status === 'ONLINE') {
                beacon.className = 'beacon online';
                title.textContent = '● ONLINE';
                subtitle.textContent = 'Your internet connection is operating normally';
            } else {
                beacon.className = 'beacon offline';
                title.textContent = '● OFFLINE';
                subtitle.textContent = 'Internet connection unavailable / Probes failing';
            }

            document.getElementById('health-score-val').textContent = statusData.health_score;
            document.getElementById('session-uptime-text').textContent = formatSessionUptime(statusData.session_duration_seconds);
            document.getElementById('card-reliability-val').textContent = `${statusData.reliability_today}%`;

            // Stat Cards
            const pingVal = statusData.latency !== null ? `${statusData.latency} ms` : 'Offline';
            document.getElementById('card-ping-val').textContent = pingVal;
            const pingBadge = document.getElementById('card-ping-badge');
            if (statusData.latency === null) {
                pingBadge.textContent = 'Critical';
                pingBadge.className = 'badge critical';
            } else if (statusData.latency < 40) {
                pingBadge.textContent = 'Excellent';
                pingBadge.className = 'badge excellent';
            } else if (statusData.latency < 90) {
                pingBadge.textContent = 'Good';
                pingBadge.className = 'badge good';
            } else {
                pingBadge.textContent = 'High';
                pingBadge.className = 'badge warning';
            }

            const lossVal = statusData.packet_loss !== null ? `${statusData.packet_loss}%` : '100%';
            document.getElementById('card-loss-val').textContent = lossVal;
            const lossBadge = document.getElementById('card-loss-badge');
            if (statusData.packet_loss === 0) {
                lossBadge.textContent = 'Excellent';
                lossBadge.className = 'badge excellent';
            } else if (statusData.packet_loss <= 5) {
                lossBadge.textContent = 'Warning';
                lossBadge.className = 'badge warning';
            } else {
                lossBadge.textContent = 'Poor';
                lossBadge.className = 'badge critical';
            }

            const dnsVal = statusData.dns_time !== null ? `${statusData.dns_time} ms` : 'Failed';
            document.getElementById('card-dns-val').textContent = dnsVal;
            const dnsBadge = document.getElementById('card-dns-badge');
            if (statusData.dns_time !== null && statusData.dns_time < 50) {
                dnsBadge.textContent = 'Fast';
                dnsBadge.className = 'badge excellent';
            } else {
                dnsBadge.textContent = 'Normal';
                dnsBadge.className = 'badge good';
            }

            // Update Metrics Chart
            const metricsRes = await fetch('/api/metrics');
            const metricsData = await metricsRes.json();

            if (latencyChart && metricsData.length > 0) {
                latencyChart.data.labels = metricsData.map(m => formatTime(m.timestamp));
                latencyChart.data.datasets[0].data = metricsData.map(m => m.latency);
                latencyChart.data.datasets[1].data = metricsData.map(m => m.dns_time);
                latencyChart.update('none');
            }
        } catch (err) {
            console.error('Telemetry fetch error:', err);
        }
    }

    // Statistics View
    const tabBtns = document.querySelectorAll('.btn-tab');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedStatsDays = parseInt(btn.getAttribute('data-days'));
            fetchStatistics(selectedStatsDays);
        });
    });

    async function fetchStatistics(days) {
        try {
            const res = await fetch(`/api/statistics?days=${days}`);
            const data = await res.json();

            document.getElementById('stats-uptime').textContent = `${data.uptime_percentage}%`;
            document.getElementById('stats-outages-count').textContent = data.outage_count;
            document.getElementById('stats-downtime').textContent = formatDuration(data.total_downtime_sec);
            document.getElementById('stats-longest-outage').textContent = formatDuration(data.longest_outage_sec);
            document.getElementById('stats-avg-ping').textContent = `${data.avg_latency} ms`;
            document.getElementById('stats-min-max-ping').textContent = `${data.min_latency} / ${data.max_latency} ms`;
            document.getElementById('stats-avg-loss').textContent = `${data.avg_packet_loss}%`;
            document.getElementById('stats-avg-dns').textContent = `${data.avg_dns_time} ms`;
        } catch (err) {
            console.error('Error loading stats:', err);
        }
    }

    // Outages View
    async function fetchOutages() {
        try {
            const res = await fetch('/api/outages');
            const outages = await res.json();
            const container = document.getElementById('outages-timeline-list');

            if (outages.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <p>No outages recorded. Connection has been clean!</p>
                    </div>`;
                return;
            }

            container.innerHTML = outages.map(o => `
                <div class="timeline-item ${o.status === 'RESOLVED' ? 'resolved' : ''}">
                    <div class="timeline-content">
                        <div class="timeline-time">
                            ${formatTime(o.start_time)} ${o.end_time ? '→ ' + formatTime(o.end_time) : '(Ongoing)'}
                        </div>
                        <div class="timeline-duration">
                            Status: <strong>${o.status}</strong> | Duration: ${formatDuration(o.duration_seconds)}
                        </div>
                    </div>
                </div>
            `).join('');
        } catch (err) {
            console.error('Error fetching outages:', err);
        }
    }

    // Speed Test
    const btnSpeedtest = document.getElementById('btn-start-speedtest');
    btnSpeedtest.addEventListener('click', async () => {
        btnSpeedtest.disabled = true;
        btnSpeedtest.textContent = 'Testing...';
        document.getElementById('speed-val').textContent = '...';

        try {
            const res = await fetch('/api/speedtest', { method: 'POST' });
            const data = await res.json();

            if (data.status === 'success') {
                document.getElementById('speed-val').textContent = data.download_speed_mbps.toFixed(2);
                document.getElementById('speed-duration').textContent = `${data.duration_seconds}s`;
                document.getElementById('speed-bytes').textContent = `${(data.bytes_received / 1024).toFixed(1)} KB`;
                document.getElementById('speed-time').textContent = formatTime(data.timestamp);
            } else {
                alert('Speed test failed');
            }
        } catch (err) {
            alert('Error running speed test');
        } finally {
            btnSpeedtest.disabled = false;
            btnSpeedtest.textContent = 'Start Speed Test';
        }
    });

    // Settings
    async function loadSettings() {
        try {
            const res = await fetch('/api/settings');
            const data = await res.json();
            document.getElementById('setting-interval').value = data.interval;
            document.getElementById('setting-ping-target').value = data.ping_target;
            document.getElementById('setting-dns-target').value = data.dns_target;
            document.getElementById('setting-retention').value = data.retention_days;
            document.getElementById('setting-graph-points').value = data.max_graph_points;
        } catch (err) {
            console.error('Error loading settings:', err);
        }
    }

    const settingsForm = document.getElementById('settings-form');
    settingsForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            interval: document.getElementById('setting-interval').value,
            ping_target: document.getElementById('setting-ping-target').value,
            dns_target: document.getElementById('setting-dns-target').value,
            retention_days: document.getElementById('setting-retention').value,
            max_graph_points: document.getElementById('setting-graph-points').value
        };

        try {
            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.status === 'success') {
                const msg = document.getElementById('settings-save-status');
                msg.textContent = 'Settings saved!';
                setTimeout(() => { msg.textContent = ''; }, 3000);
            }
        } catch (err) {
            alert('Failed to save settings');
        }
    });

    // Init
    initChart();
    updateDashboard();
    setInterval(updateDashboard, 3000);
});