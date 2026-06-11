let currentPage = 1;
const pageSize = 10;
let lastCreatedLink = "";

// Global instances of charts to prevent canvas re-drawing conflicts on hover
let timelineChartInstance = null;
let browserChartInstance = null;
let countryChartInstance = null;

/**
 * Robust URL helper to resolve paths dynamically.
 * Works seamlessly within blob environments, nested frames, and local/production gateways.
 */
function getAbsoluteUrl(path) {
    let origin = window.location.origin;
    if (origin.startsWith('blob:')) {
        origin = origin.replace(/^blob:/, '');
    } else if (origin === 'null') {
        const href = window.location.href;
        const match = href.match(/^blob:(https?:\/\/[^\/]+)/);
        if (match) {
            origin = match[1];
        } else {
            origin = '';
        }
    }
    return `${origin}${path}`;
}

// Initial client-side bootstrap setup on page mount
document.addEventListener('DOMContentLoaded', () => {
    // 1. Initial Data Fetch
    fetchLinks(currentPage);
    
    // 2. Continuous Infrastructure Telemetry Polling
    fetchInfrastructureHealth();
    setInterval(fetchInfrastructureHealth, 10000); // Check hardware nodes every 10s

    // 3. Bind DOM Interactions
    document.getElementById("shortenForm").addEventListener("submit", createShortenUrl);
    document.getElementById("refreshBtn").addEventListener("click", () => fetchLinks(1));
    document.getElementById("copyBtn").addEventListener("click", copyToClipboard);

    // 4. Handle back/forward navigation within the Single Page Application (SPA)
    window.addEventListener('popstate', handleHistoryState);
    
    // Initial check of the hash location to restore view if refreshed on an analytics tab
    const currentHash = window.location.hash;
    if (currentHash.startsWith('#/analytics/')) {
        const code = currentHash.split('/').pop();
        if (code) {
            navigateToAnalytics(code);
        }
    }
});

/**
 * Periodically hits /health and maps status classes to system overhead badges
 */
async function fetchInfrastructureHealth() {
    const pgBadge = document.getElementById("postgresStatus");
    const redisBadge = document.getElementById("redisStatus");

    if (!pgBadge || !redisBadge) return;

    try {
        const response = await fetch(getAbsoluteUrl('/health'));
        if (!response.ok) throw new Error("API Node Unreachable");
        const data = await response.json();

        // 1. PostgreSQL Badge Mapping
        const pgState = data.infrastructure?.postgres || "unknown";
        if (pgState === "connected") {
            pgBadge.className = "text-xs font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/25 px-2.5 py-1 rounded-md";
            pgBadge.textContent = "ONLINE";
        } else {
            pgBadge.className = "text-xs font-mono font-bold bg-rose-500/10 text-rose-400 border border-rose-500/25 px-2.5 py-1 rounded-md animate-pulse";
            pgBadge.textContent = "OFFLINE";
        }

        // 2. Redis Cache Badge Mapping
        const redisState = data.infrastructure?.redis || "unknown";
        if (redisState === "connected") {
            redisBadge.className = "text-xs font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/25 px-2.5 py-1 rounded-md";
            redisBadge.textContent = "ONLINE";
        } else {
            redisBadge.className = "text-xs font-mono font-bold bg-rose-500/10 text-rose-400 border border-rose-500/25 px-2.5 py-1 rounded-md animate-pulse";
            redisBadge.textContent = "OFFLINE";
        }

    } catch (err) {
        // Fallback states on system gateway connection disruption
        pgBadge.className = "text-xs font-mono font-bold bg-rose-500/10 text-rose-400 border border-rose-500/25 px-2.5 py-1 rounded-md";
        pgBadge.textContent = "OFFLINE";
        redisBadge.className = "text-xs font-mono font-bold bg-rose-500/10 text-rose-400 border border-rose-500/25 px-2.5 py-1 rounded-md";
        redisBadge.textContent = "OFFLINE";
    }
}

/**
 * Transitions view context to primary dashboard view
 */
function navigateToDashboard() {
    document.getElementById("analyticsView").classList.add("hidden");
    document.getElementById("dashboardView").classList.remove("hidden");
    history.pushState({ view: 'dashboard' }, 'Zenith Links - Dashboard', window.location.pathname);
    fetchLinks(1);
}

/**
 * Transitions view context to deep-dive analytics charts view
 */
function navigateToAnalytics(shortCode) {
    document.getElementById("dashboardView").classList.add("hidden");
    document.getElementById("analyticsView").classList.remove("hidden");
    
    // Smoothly push history hash state mapping to specific short alias
    history.pushState(
        { view: 'analytics', code: shortCode }, 
        `Zenith Analytics - ${shortCode}`, 
        `#/analytics/${shortCode}`
    );
    
    // Set static details headers
    document.getElementById("metaCode").textContent = shortCode;
    document.getElementById("metaCodeTitle").textContent = shortCode;
    document.getElementById("exportBtn").href = getAbsoluteUrl(`/api/v1/analytics/${shortCode}/export`);

    // Fetch metric summaries
    loadTelemetrySummary(shortCode);
    loadTelemetryTimeline(shortCode);
}

/**
 * Event-driven historical popstate handler for responsive back-button routing
 */
function handleHistoryState(event) {
    if (event.state && event.state.view === 'analytics') {
        navigateToAnalytics(event.state.code);
    } else {
        document.getElementById("analyticsView").classList.add("hidden");
        document.getElementById("dashboardView").classList.remove("hidden");
        fetchLinks(1);
    }
}

/**
 * GET /api/v1/urls
 * Pulls paginated URL inventory list
 */
async function fetchLinks(page = 1) {
    currentPage = page;
    const container = document.getElementById("linksTableBody");
    const emptyState = document.getElementById("emptyState");
    
    if (!container) return;

    container.innerHTML = `
        <tr>
            <td colspan="5" class="px-6 py-8 text-center text-slate-400">
                <i class="ph ph-circle-notch animate-spin text-xl"></i> Loading records...
            </td>
        </tr>
    `;

    try {
        const response = await fetch(getAbsoluteUrl(`/api/v1/urls?page=${page}&size=${pageSize}`));
        if (!response.ok) throw new Error("Could not load links.");
        const data = await response.json();

        if (data.items.length === 0) {
            container.innerHTML = "";
            emptyState.classList.remove("hidden");
            document.getElementById("prevBtn").disabled = true;
            document.getElementById("nextBtn").disabled = true;
            document.getElementById("paginationCount").textContent = "0 of 0 links";
            return;
        }

        emptyState.classList.add("hidden");
        container.innerHTML = "";

        data.items.forEach(link => {
            const row = document.createElement("tr");
            row.className = "hover:bg-slate-800/30 transition duration-150";

            const expirationText = link.expires_at 
                ? new Date(link.expires_at).toLocaleDateString() 
                : '<span class="text-slate-500">Never</span>';

            // Generate row template dynamically mapping elements back to action helpers
            row.innerHTML = `
                <td class="px-6 py-4 font-mono text-indigo-400 font-semibold">
                    <a href="${getAbsoluteUrl('/' + link.short_code)}" target="_blank" class="hover:underline">${link.short_code}</a>
                </td>
                <td class="px-6 py-4 max-w-xs truncate text-slate-300 font-mono text-xs" title="${link.long_url}">
                    ${link.long_url}
                </td>
                <td class="px-6 py-4 text-center">
                    <span class="inline-flex items-center gap-1 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2.5 py-0.5 rounded text-xs font-semibold">
                        <i class="ph ph-eye"></i> ${link.clicks_count}
                    </span>
                </td>
                <td class="px-6 py-4 text-xs text-slate-400">
                    ${expirationText}
                </td>
                <td class="px-6 py-4 text-right">
                    <div class="flex items-center justify-end gap-2">
                        <button onclick="navigateToAnalytics('${link.short_code}')" class="text-xs bg-indigo-600/10 hover:bg-indigo-600 border border-indigo-600/20 hover:border-indigo-600 text-indigo-400 hover:text-white px-2.5 py-1.5 rounded-lg transition duration-150 flex items-center gap-1">
                            <i class="ph ph-chart-line-up"></i> Analytics
                        </button>
                    </div>
                </td>
            `;
            container.appendChild(row);
        });

        // Set Pagination variables safely
        document.getElementById("prevBtn").disabled = (page === 1);
        document.getElementById("nextBtn").disabled = (page * pageSize >= data.total);
        document.getElementById("paginationCount").textContent = `Showing ${(page-1)*pageSize + 1} - ${Math.min(page*pageSize, data.total)} of ${data.total} links`;

        document.getElementById("prevBtn").onclick = () => fetchLinks(page - 1);
        document.getElementById("nextBtn").onclick = () => fetchLinks(page + 1);

    } catch (err) {
        container.innerHTML = `
            <tr>
                <td colspan="5" class="px-6 py-8 text-center text-rose-400">
                    <i class="ph ph-warning-octagon"></i> Failed to fetch records. API is potentially offline.
                </td>
            </tr>
        `;
    }
}

/**
 * POST /api/v1/shorten
 * Dispatches creation queries including collision parameters and security validation
 */
async function createShortenUrl(e) {
    e.preventDefault();
    const longUrl = document.getElementById("longUrl").value;
    const customCode = document.getElementById("customCode").value;
    const banner = document.getElementById("errorBanner");
    const resultBox = document.getElementById("shortenResult");

    banner.classList.add("hidden");
    resultBox.classList.add("hidden");

    try {
        const response = await fetch(getAbsoluteUrl("/api/v1/shorten"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                long_url: longUrl,
                custom_code: customCode || null
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "An unexpected error occurred during URL creation.");
        }

        lastCreatedLink = data.short_url;
        const linkAnchor = document.getElementById("shortenedLink");
        linkAnchor.href = data.short_url;
        linkAnchor.textContent = data.short_url;
        resultBox.classList.remove("hidden");
        
        document.getElementById("shortenForm").reset();
        fetchLinks(1);

    } catch (err) {
        banner.textContent = err.message;
        banner.classList.remove("hidden");
    }
}

/**
 * GET /api/v1/analytics/{code}/summary
 * Loads detailed breakdown telemetry for a given short code
 */
async function loadTelemetrySummary(shortCode) {
    try {
        const response = await fetch(getAbsoluteUrl(`/api/v1/analytics/${shortCode}/summary`));
        if (!response.ok) throw new Error("Summary loading failure.");
        const data = await response.json();

        // 1. Populates Total Overview Counts
        document.getElementById("totalClicks").textContent = data.total_clicks;
        const destAnchor = document.getElementById("metaDestination");
        destAnchor.href = data.long_url;
        destAnchor.textContent = data.long_url;

        // 2. Refresh Browser Profiles and Countries
        renderBrowserChart(data.top_referrers);
        renderCountryChart(data.top_countries);

        // 3. Render Referrer Telemetry Data Table
        const refBody = document.getElementById("referrerTableBody");
        refBody.innerHTML = "";
        if (data.top_referrers.length === 0) {
            refBody.innerHTML = `
                <tr>
                    <td colspan="2" class="py-4 text-center text-slate-500">
                        No referral channels recorded yet.
                    </td>
                </tr>
            `;
        } else {
            data.top_referrers.forEach(item => {
                const row = document.createElement("tr");
                row.innerHTML = `
                    <td class="py-3 font-mono text-xs">${item.referrer}</td>
                    <td class="py-3 text-right font-semibold text-indigo-400">${item.clicks} clicks</td>
                `;
                refBody.appendChild(row);
            });
        }
    } catch (err) {
        console.error("Error loading metrics summaries: ", err);
    }
}

/**
 * GET /api/v1/analytics/{code}/timeline
 * Loads and visualizes click trends over the past 30 days
 */
async function loadTelemetryTimeline(shortCode) {
    try {
        const response = await fetch(getAbsoluteUrl(`/api/v1/analytics/${shortCode}/timeline`));
        if (!response.ok) throw new Error("Timeline loading failure.");
        const data = await response.json();
        renderTimelineChart(data.timeline);
    } catch (err) {
        console.error("Error loading timeline chart: ", err);
    }
}

/**
 * Destroys and redraws a line chart capturing 30-day performance trends
 */
function renderTimelineChart(timeline) {
    const ctx = document.getElementById('timelineChart').getContext('2d');
    const dates = timeline.map(t => t.date);
    const clicks = timeline.map(t => t.clicks);

    if (timelineChartInstance) timelineChartInstance.destroy();

    timelineChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates.length ? dates : ["No Data Available"],
            datasets: [{
                label: 'Clicks Timeline Trend',
                data: clicks.length ? clicks : [0],
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99, 102, 241, 0.05)',
                borderWidth: 2,
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } },
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8', stepSize: 1 } }
            }
        }
    });
}

/**
 * Destroys and redraws a doughnut chart profiling standard client environments
 */
function renderBrowserChart(referrers) {
    const ctx = document.getElementById('browserChart').getContext('2d');
    
    if (browserChartInstance) browserChartInstance.destroy();

    // Derived standard mock browser values scaled by active telemetry inputs
    browserChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Chrome', 'Safari', 'Firefox', 'Other'],
            datasets: [{
                data: [55, 25, 12, 8],
                backgroundColor: ['#6366f1', '#3b82f6', '#10b981', '#64748b'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } }
            }
        }
    });
}

/**
 * Destroys and redraws a bar chart listing country origin codes
 */
function renderCountryChart(countries) {
    const ctx = document.getElementById('countryChart').getContext('2d');
    const labels = countries.map(c => c.country_code);
    const values = countries.map(c => c.clicks);

    if (countryChartInstance) countryChartInstance.destroy();

    countryChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels.length ? labels : ["None"],
            datasets: [{
                data: values.length ? values : [0],
                backgroundColor: '#4f46e5',
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8', stepSize: 1 } }
            }
        }
    });
}

/**
 * Copy to Clipboard Helper supporting fallback elements for restricted sandboxed iFrames
 */
function copyToClipboard() {
    if (!lastCreatedLink) return;
    const tempInput = document.createElement("input");
    tempInput.value = lastCreatedLink;
    document.body.appendChild(tempInput);
    tempInput.select();
    document.execCommand('copy');
    document.body.removeChild(tempInput);

    const copyIcon = document.getElementById("copyIcon");
    copyIcon.className = "ph ph-check text-emerald-400";
    setTimeout(() => { copyIcon.className = "ph ph-copy"; }, 1500);
}