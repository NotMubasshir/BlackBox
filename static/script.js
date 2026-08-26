document.addEventListener("DOMContentLoaded", () => {

    let latencyChart = null;
    let selectedStatsDays = 1;
    let speedProgressTimer = null;


    const $ = (id) =>
        document.getElementById(id);


    /* ---------------- NAVIGATION ---------------- */

    document.querySelectorAll(".nav-item").forEach(
        (item) => {

            item.addEventListener(
                "click",
                () => {

                    const target =
                        item.dataset.target;

                    document
                        .querySelectorAll(".nav-item")
                        .forEach(
                            n =>
                                n.classList.remove(
                                    "active"
                                )
                        );

                    document
                        .querySelectorAll(
                            ".view-section"
                        )
                        .forEach(
                            v =>
                                v.classList.remove(
                                    "active"
                                )
                        );

                    item.classList.add(
                        "active"
                    );

                    $(target)?.classList.add(
                        "active"
                    );


                    if (
                        target ===
                        "view-statistics"
                    ) {
                        fetchStatistics(
                            selectedStatsDays
                        );
                    }


                    if (
                        target ===
                        "view-outages"
                    ) {
                        fetchOutages();
                    }


                    if (
                        target ===
                        "view-settings"
                    ) {
                        loadSettings();
                    }

                }
            );

        }
    );


    /* ---------------- FORMATTING ---------------- */

    function formatTime(
        isoString
    ) {

        if (!isoString)
            return "--";

        const d =
            new Date(
                isoString
            );

        return d.toLocaleTimeString(
            [],
            {
                hour:
                    "2-digit",

                minute:
                    "2-digit",

                second:
                    "2-digit"
            }
        );
    }


    function formatDuration(
        seconds
    ) {

        if (
            seconds === null ||
            seconds === undefined
        ) {
            return "Ongoing";
        }

        seconds =
            Math.max(
                0,
                Math.round(
                    Number(seconds)
                )
            );

        const hours =
            Math.floor(
                seconds / 3600
            );

        const mins =
            Math.floor(
                (seconds % 3600) / 60
            );

        const secs =
            seconds % 60;


        if (hours)
            return `${hours}h ${mins}m`;

        if (mins)
            return `${mins}m ${secs}s`;

        return `${secs}s`;
    }


    function formatUptime(
        totalSeconds
    ) {

        totalSeconds =
            Math.max(
                0,
                Number(totalSeconds) || 0
            );

        const h =
            Math.floor(
                totalSeconds / 3600
            );

        const m =
            Math.floor(
                (totalSeconds % 3600) / 60
            );

        const s =
            Math.floor(
                totalSeconds % 60
            );


        return (
            `${String(h).padStart(2, "0")}:` +
            `${String(m).padStart(2, "0")}:` +
            `${String(s).padStart(2, "0")}`
        );
    }


    function setMetricNote(
        id,
        text,
        type = ""
    ) {

        const el = $(id);

        el.textContent =
            text;

        el.className =
            `metric-note ${type}`;
    }


    /* ---------------- CHART ---------------- */

    function initChart() {

        const canvas =
            $("liveLatencyChart");

        if (
            !canvas ||
            typeof Chart === "undefined"
        ) {
            return;
        }


        const ctx =
            canvas.getContext(
                "2d"
            );


        latencyChart =
            new Chart(
                ctx,
                {
                    type:
                        "line",

                    data:
                        {
                            labels:
                                [],

                            datasets:
                                [
                                    {
                                        label:
                                            "Ping",

                                        data:
                                            [],

                                        borderColor:
                                            "#42e6d0",

                                        backgroundColor:
                                            "rgba(66,230,208,.08)",

                                        borderWidth:
                                            2,

                                        pointRadius:
                                            0,

                                        pointHoverRadius:
                                            4,

                                        tension:
                                            .38,

                                        fill:
                                            true
                                    },

                                    {
                                        label:
                                            "DNS",

                                        data:
                                            [],

                                        borderColor:
                                            "#6fa8ff",

                                        borderWidth:
                                            1.5,

                                        pointRadius:
                                            0,

                                        tension:
                                            .38
                                    }
                                ]
                        },

                    options:
                        {
                            responsive:
                                true,

                            maintainAspectRatio:
                                false,

                            interaction:
                                {
                                    intersect:
                                        false,

                                    mode:
                                        "index"
                                },

                            plugins:
                                {
                                    legend:
                                        {
                                            labels:
                                                {
                                                    color:
                                                        "#9aa7b4",

                                                    boxWidth:
                                                        10,

                                                    usePointStyle:
                                                        true,

                                                    font:
                                                        {
                                                            size:
                                                                10
                                                        }
                                                }
                                        }
                                },

                            scales:
                                {
                                    x:
                                        {
                                            grid:
                                                {
                                                    color:
                                                        "rgba(255,255,255,.035)"
                                                },

                                            ticks:
                                                {
                                                    color:
                                                        "#647180",

                                                    maxTicksLimit:
                                                        7,

                                                    font:
                                                        {
                                                            size:
                                                                9
                                                        }
                                                }
                                        },

                                    y:
                                        {
                                            beginAtZero:
                                                true,

                                            grid:
                                                {
                                                    color:
                                                        "rgba(255,255,255,.035)"
                                                },

                                            ticks:
                                                {
                                                    color:
                                                        "#647180",

                                                    font:
                                                        {
                                                            size:
                                                                9
                                                        }
                                                }
                                        }
                                }
                        }
                }
            );
    }


    /* ---------------- DASHBOARD ---------------- */

    async function updateDashboard() {

        try {

            const [
                statusRes,
                metricsRes
            ] = await Promise.all(
                [
                    fetch(
                        "/api/status",
                        {
                            cache:
                                "no-store"
                        }
                    ),

                    fetch(
                        "/api/metrics",
                        {
                            cache:
                                "no-store"
                        }
                    )
                ]
            );


            if (
                !statusRes.ok ||
                !metricsRes.ok
            ) {
                throw new Error(
                    "Server response failed"
                );
            }


            const status =
                await statusRes.json();

            const metrics =
                await metricsRes.json();


            const online =
                status.status ===
                "ONLINE";


            $("status-beacon").className =
                `status-dot ${
                    online
                        ? "online"
                        : "offline"
                }`;


            $("side-dot").style.background =
                online
                    ? "var(--green)"
                    : "var(--red)";


            $("status-title").textContent =
                online
                    ? "Your internet is working"
                    : "Internet connection is down";


            $("status-subtitle").textContent =
                online
                    ? "Everything looks normal right now"
                    : "The monitor cannot reach the network";


            $("health-score-val").textContent =
                status.health_score ??
                "--";


            $("health-ring").style.setProperty(
                "--health",
                `${
                    (Number(
                        status.health_score
                    ) || 0)
                    * 3.6
                }deg`
            );


            $("session-uptime-text").textContent =
                formatUptime(
                    status.session_duration_seconds
                );


            /* Ping */

            if (
                status.latency !== null &&
                status.latency !== undefined
            ) {

                $("card-ping-val").textContent =
                    `${Number(
                        status.latency
                    ).toFixed(1)} ms`;


                if (
                    status.latency < 40
                ) {

                    setMetricNote(
                        "card-ping-badge",
                        "Excellent response",
                        "excellent"
                    );

                } else if (
                    status.latency < 90
                ) {

                    setMetricNote(
                        "card-ping-badge",
                        "Good response",
                        "good"
                    );

                } else {

                    setMetricNote(
                        "card-ping-badge",
                        "A little slow",
                        "warning"
                    );
                }

            } else {

                $("card-ping-val").textContent =
                    "Offline";

                setMetricNote(
                    "card-ping-badge",
                    "No response",
                    "critical"
                );
            }


            /* Packet loss */

            if (
                status.packet_loss !== null &&
                status.packet_loss !== undefined
            ) {

                $("card-loss-val").textContent =
                    `${Number(
                        status.packet_loss
                    ).toFixed(1)}%`;


                if (
                    status.packet_loss === 0
                ) {

                    setMetricNote(
                        "card-loss-badge",
                        "No loss detected",
                        "excellent"
                    );

                } else if (
                    status.packet_loss <= 5
                ) {

                    setMetricNote(
                        "card-loss-badge",
                        "Some packets lost",
                        "warning"
                    );

                } else {

                    setMetricNote(
                        "card-loss-badge",
                        "High packet loss",
                        "critical"
                    );
                }
            }


            /* DNS */

            if (
                status.dns_time !== null &&
                status.dns_time !== undefined
            ) {

                $("card-dns-val").textContent =
                    `${Number(
                        status.dns_time
                    ).toFixed(1)} ms`;


                if (
                    status.dns_time < 50
                ) {

                    setMetricNote(
                        "card-dns-badge",
                        "Fast lookup",
                        "excellent"
                    );

                } else if (
                    status.dns_time < 100
                ) {

                    setMetricNote(
                        "card-dns-badge",
                        "Normal lookup",
                        "good"
                    );

                } else {

                    setMetricNote(
                        "card-dns-badge",
                        "Slow lookup",
                        "warning"
                    );
                }

            } else {

                $("card-dns-val").textContent =
                    "Failed";

                setMetricNote(
                    "card-dns-badge",
                    "DNS did not respond",
                    "critical"
                );
            }


            $("card-reliability-val").textContent =
                `${Number(
                    status.reliability_today || 0
                ).toFixed(1)}%`;


            /* Chart */

            if (latencyChart) {

                latencyChart.data.labels =
                    metrics.map(
                        m =>
                            formatTime(
                                m.timestamp
                            )
                    );


                latencyChart.data.datasets[0].data =
                    metrics.map(
                        m =>
                            m.latency
                    );


                latencyChart.data.datasets[1].data =
                    metrics.map(
                        m =>
                            m.dns_time
                    );


                latencyChart.update(
                    "none"
                );
            }

        } catch (error) {

            console.error(
                "Dashboard update failed:",
                error
            );
        }
    }


    /* ---------------- STATISTICS ---------------- */

    document
        .querySelectorAll(".btn-tab")
        .forEach(
            (btn) => {

                btn.addEventListener(
                    "click",
                    () => {

                        document
                            .querySelectorAll(
                                ".btn-tab"
                            )
                            .forEach(
                                b =>
                                    b.classList.remove(
                                        "active"
                                    )
                            );

                        btn.classList.add(
                            "active"
                        );

                        selectedStatsDays =
                            Number(
                                btn.dataset.days
                            );

                        fetchStatistics(
                            selectedStatsDays
                        );
                    }
                );
            }
        );


    async function fetchStatistics(
        days
    ) {

        try {

            const res =
                await fetch(
                    `/api/statistics?days=${days}`,
                    {
                        cache:
                            "no-store"
                    }
                );


            const data =
                await res.json();


            $("stats-uptime").textContent =
                `${data.uptime_percentage}%`;


            $("stats-outages-count").textContent =
                data.outage_count;


            $("stats-downtime").textContent =
                formatDuration(
                    data.total_downtime_sec
                );


            $("stats-longest-outage").textContent =
                formatDuration(
                    data.longest_outage_sec
                );


            $("stats-avg-ping").textContent =
                `${data.avg_latency} ms`;


            $("stats-min-max-ping").textContent =
                `${data.min_latency} / ${data.max_latency} ms`;


            $("stats-avg-loss").textContent =
                `${data.avg_packet_loss}%`;


            $("stats-avg-dns").textContent =
                `${data.avg_dns_time} ms`;

        } catch (error) {

            console.error(
                "Statistics failed:",
                error
            );
        }
    }


    /* ---------------- OUTAGES ---------------- */

    async function fetchOutages() {

        try {

            const res =
                await fetch(
                    "/api/outages",
                    {
                        cache:
                            "no-store"
                    }
                );


            const outages =
                await res.json();


            const container =
                $("outages-timeline-list");


            if (!outages.length) {

                container.innerHTML =
                    `
                    <div class="empty-state">
                        No outages recorded.
                        Your connection has been clean.
                    </div>
                    `;

                return;
            }


            container.innerHTML =
                outages.map(
                    o =>
                        `
                        <div class="timeline-item ${
                            o.status === "RESOLVED"
                                ? "resolved"
                                : ""
                        }">

                            <span class="timeline-dot"></span>

                            <div class="timeline-main">

                                <b>
                                    ${
                                        o.status === "RESOLVED"
                                            ? "Connection recovered"
                                            : "Connection is still down"
                                    }
                                </b>

                                <p>
                                    ${formatTime(
                                        o.start_time
                                    )}

                                    ${
                                        o.end_time
                                            ? `→ ${formatTime(
                                                o.end_time
                                            )}`
                                            : "→ ongoing"
                                    }
                                </p>

                            </div>

                            <span class="timeline-duration">
                                ${formatDuration(
                                    o.duration_seconds
                                )}
                            </span>

                        </div>
                        `
                ).join("");

        } catch (error) {

            console.error(
                "Outages failed:",
                error
            );
        }
    }


    /* ---------------- SPEED TEST ---------------- */

    function setSpeedProgress(
        value,
        label = null
    ) {

        const pct =
            Math.max(
                0,
                Math.min(
                    100,
                    value
                )
            );


        $("speed-progress-fill")
            .style.width =
                `${pct}%`;


        $("speedometer")
            .style.setProperty(
                "--progress",
                `${pct * 3.6}deg`
            );


        $("speed-progress-text")
            .textContent =
                `${Math.round(
                    pct
                )}%`;


        $("speed-percent")
            .textContent =
                label ??
                `${Math.round(
                    pct
                )}%`;
    }


    $("btn-start-speedtest")
        .addEventListener(
            "click",
            async () => {

                const button =
                    $("btn-start-speedtest");


                button.disabled =
                    true;


                button.innerHTML =
                    "<span>◌</span> Testing…";


                $("speed-state")
                    .textContent =
                        "Measuring download speed…";


                $("speed-live-time")
                    .textContent =
                        "Please wait";


                $("speed-error")
                    .classList.remove(
                        "show"
                    );


                $("speed-ping")
                    .textContent =
                        "Testing";


                $("speed-bytes")
                    .textContent =
                        "Receiving";


                $("speed-duration")
                    .textContent =
                        "Running";


                $("speed-val")
                    .textContent =
                        "—";


                setSpeedProgress(
                    2,
                    "Connecting"
                );


                const started =
                    performance.now();


                let progress = 2;


                speedProgressTimer =
                    setInterval(
                        () => {

                            const elapsed =
                                (
                                    performance.now()
                                    -
                                    started
                                )
                                /
                                1000;


                            progress =
                                Math.min(
                                    94,
                                    2 +
                                    92 *
                                    (
                                        1 -
                                        Math.exp(
                                            -elapsed / 4
                                        )
                                    )
                                );


                            setSpeedProgress(
                                progress,
                                "Measuring"
                            );


                            $("speed-live-time")
                                .textContent =
                                    `${elapsed.toFixed(
                                        1
                                    )}s elapsed`;

                        },
                        120
                    );


                try {

                    const res =
                        await fetch(
                            "/api/speedtest",
                            {
                                method:
                                    "POST",

                                cache:
                                    "no-store"
                            }
                        );


                    const data =
                        await res.json();


                    if (
                        !res.ok ||
                        data.status !==
                            "success"
                    ) {

                        throw new Error(
                            data.message ||
                            "Speed test failed."
                        );
                    }


                    clearInterval(
                        speedProgressTimer
                    );


                    setSpeedProgress(
                        100,
                        "Complete"
                    );


                    $("speed-state")
                        .textContent =
                            "Test complete";


                    $("speed-live-time")
                        .textContent =
                            "Finished";


                    $("speed-val")
                        .textContent =
                            Number(
                                data.download_speed_mbps
                            ).toFixed(2);


                    $("speed-ping")
                        .textContent =
                            data.latency_ms ==
                            null

                                ? "--"

                                : Number(
                                    data.latency_ms
                                ).toFixed(1);


                    $("speed-bytes")
                        .textContent =
                            `${
                                (
                                    Number(
                                        data.bytes_received
                                    )
                                    /
                                    1024
                                    /
                                    1024
                                ).toFixed(1)
                            } MB`;


                    $("speed-duration")
                        .textContent =
                            `${
                                Number(
                                    data.duration_seconds
                                ).toFixed(1)
                            }s`;

                } catch (error) {

                    clearInterval(
                        speedProgressTimer
                    );


                    setSpeedProgress(
                        0,
                        "Failed"
                    );


                    $("speed-state")
                        .textContent =
                            "Test failed";


                    $("speed-live-time")
                        .textContent =
                            "Try again";


                    $("speed-val")
                        .textContent =
                            "0.00";


                    $("speed-ping")
                        .textContent =
                            "--";


                    $("speed-bytes")
                        .textContent =
                            "--";


                    $("speed-duration")
                        .textContent =
                            "--";


                    $("speed-error")
                        .textContent =
                            error.message;


                    $("speed-error")
                        .classList.add(
                            "show"
                        );

                } finally {

                    button.disabled =
                        false;


                    button.innerHTML =
                        "<span>↯</span> Run speed test again";
                }
            }
        );


    /* ---------------- SETTINGS ---------------- */

    async function loadSettings() {

        try {

            const res =
                await fetch(
                    "/api/settings",
                    {
                        cache:
                            "no-store"
                    }
                );


            const data =
                await res.json();


            $("setting-interval").value =
                data.interval;


            $("setting-ping-target").value =
                data.ping_target;


            $("setting-dns-target").value =
                data.dns_target;


            $("setting-dns-domain").value =
                data.dns_probe_domain ||
                "example.com";


            $("setting-retention").value =
                data.retention_days;


            $("setting-graph-points").value =
                data.max_graph_points;

        } catch (error) {

            console.error(
                "Settings failed:",
                error
            );
        }
    }


    $("settings-form")
        .addEventListener(
            "submit",
            async (event) => {

                event.preventDefault();


                const status =
                    $("settings-save-status");


                status.textContent =
                    "";


                const payload = {

                    interval:
                        $("setting-interval")
                            .value,

                    ping_target:
                        $("setting-ping-target")
                            .value
                            .trim(),

                    dns_target:
                        $("setting-dns-target")
                            .value
                            .trim(),

                    dns_probe_domain:
                        $("setting-dns-domain")
                            .value
                            .trim(),

                    retention_days:
                        $("setting-retention")
                            .value,

                    max_graph_points:
                        $("setting-graph-points")
                            .value
                };


                try {

                    const res =
                        await fetch(
                            "/api/settings",
                            {
                                method:
                                    "POST",

                                headers:
                                    {
                                        "Content-Type":
                                            "application/json"
                                    },

                                body:
                                    JSON.stringify(
                                        payload
                                    )
                            }
                        );


                    const data =
                        await res.json();


                    if (!res.ok) {

                        throw new Error(
                            (
                                data.errors ||
                                [
                                    "Could not save settings."
                                ]
                            ).join(" ")
                        );
                    }


                    status.textContent =
                        "Saved.";


                    setTimeout(
                        () => {
                            status.textContent =
                                "";
                        },
                        2500
                    );

                } catch (error) {

                    status.textContent =
                        error.message;

                    status.style.color =
                        "var(--red)";
                }

            }
        );


    /* ---------------- START ---------------- */

    initChart();

    updateDashboard();

    setInterval(
        updateDashboard,
        3000
    );

});
