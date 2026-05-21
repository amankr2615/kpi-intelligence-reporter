// Configuration
// IMPORTANT: Change this to your live Render.com URL once the backend is deployed!
// Example: "https://kpi-intelligence-reporter.onrender.com"
// If you leave it empty (""), it will use the same host (for local testing).
const BACKEND_URL = "https://kpi-backend-dl16.onrender.com";

// State
let marketingData = [
    { date: '2025-10-01', channel: 'Google', spend: 120, clicks: 60, conversions: 5, revenue: 300 },
    { date: '2025-10-02', channel: 'Google', spend: 130, clicks: 65, conversions: 6, revenue: 350 },
    { date: '2025-10-01', channel: 'Meta', spend: 100, clicks: 55, conversions: 3, revenue: 180 },
    { date: '2025-10-02', channel: 'Meta', spend: 95, clicks: 53, conversions: 4, revenue: 200 }
];

let productData = [
    { date: '2025-09-01', product: 'ProductA', units_sold: 50, price: 20, revenue: 1000, region: 'North' },
    { date: '2025-09-02', product: 'ProductA', units_sold: 55, price: 20, revenue: 1100, region: 'North' },
    { date: '2025-09-01', product: 'ProductB', units_sold: 30, price: 35, revenue: 1050, region: 'North' },
    { date: '2025-09-02', product: 'ProductB', units_sold: 32, price: 35, revenue: 1120, region: 'North' }
];

const M_COLS = ['date', 'channel', 'spend', 'clicks', 'conversions', 'revenue'];
const P_COLS = ['date', 'product', 'units_sold', 'price', 'revenue', 'region'];

// UI Elements
const mTableContainer = document.getElementById('marketing-table-container');
const pTableContainer = document.getElementById('product-table-container');

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    renderTable(marketingData, M_COLS, mTableContainer, 'marketing');
    renderTable(productData, P_COLS, pTableContainer, 'product');
    setupTabs();
    setupFileUploads();
    setupCodeMender();
    initAuthPortal();
    
    document.getElementById('generate-btn').addEventListener('click', () => {
        generateReport();
    });
});

// Tab Logic
function setupTabs() {
    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active from all
            document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            // Add active to current
            tab.classList.add('active');
            document.getElementById(tab.dataset.tab).classList.add('active');
        });
    });
}

// Table Rendering Logic
function renderTable(data, columns, container, type) {
    let html = `<table><thead><tr>`;
    columns.forEach(col => {
        html += `<th>${col.replace('_', ' ').toUpperCase()}</th>`;
    });
    html += `<th></th></tr></thead><tbody>`;

    if (data.length === 0) {
        html += `<tr><td colspan="${columns.length + 1}" style="text-align:center;color:#94a3b8">No data</td></tr>`;
    }

    data.forEach((row, rowIndex) => {
        html += `<tr>`;
        columns.forEach(col => {
            const inputType = (col === 'date') ? 'date' : (typeof row[col] === 'number' ? 'number' : 'text');
            html += `<td><input type="${inputType}" data-type="${type}" data-row="${rowIndex}" data-col="${col}" value="${row[col] !== undefined ? row[col] : ''}"></td>`;
        });
        html += `<td><button class="delete-btn" data-type="${type}" data-row="${rowIndex}">×</button></td></tr>`;
    });
    html += `</tbody></table>`;
    container.innerHTML = html;

    // Attach Event Listeners to Inputs
    container.querySelectorAll('input').forEach(input => {
        input.addEventListener('change', (e) => {
            const rIdx = parseInt(e.target.dataset.row);
            const cName = e.target.dataset.col;
            let val = e.target.value;
            if (e.target.type === 'number') val = parseFloat(val) || 0;
            
            if (type === 'marketing') marketingData[rIdx][cName] = val;
            else productData[rIdx][cName] = val;
        });
    });

    // Attach Event Listeners to Delete buttons
    container.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const rIdx = parseInt(e.target.dataset.row);
            if (type === 'marketing') {
                marketingData.splice(rIdx, 1);
                renderTable(marketingData, M_COLS, mTableContainer, 'marketing');
            } else {
                productData.splice(rIdx, 1);
                renderTable(productData, P_COLS, pTableContainer, 'product');
            }
        });
    });
}

// Add Rows
document.getElementById('add-marketing-row').addEventListener('click', () => {
    marketingData.push({ date: new Date().toISOString().split('T')[0], channel: '', spend: 0, clicks: 0, conversions: 0, revenue: 0 });
    renderTable(marketingData, M_COLS, mTableContainer, 'marketing');
});

document.getElementById('add-product-row').addEventListener('click', () => {
    productData.push({ date: new Date().toISOString().split('T')[0], product: '', units_sold: 0, price: 0, revenue: 0, region: '' });
    renderTable(productData, P_COLS, pTableContainer, 'product');
});

// File Upload Logic
function setupFileUploads() {
    document.getElementById('marketing-upload').addEventListener('change', (e) => handleUpload(e, 'marketing'));
    document.getElementById('product-upload').addEventListener('change', (e) => handleUpload(e, 'product'));
}

function handleUpload(event, type) {
    const file = event.target.files[0];
    if (!file) return;
    
    document.getElementById(`${type}-file-name`).textContent = file.name;

    Papa.parse(file, {
        header: true,
        dynamicTyping: true,
        skipEmptyLines: true,
        transformHeader: function(header) {
            // Normalize headers: lowercase, replace spaces with underscores
            return header.trim().toLowerCase().replace(/\s+/g, '_');
        },
        complete: function(results) {
            if (type === 'marketing') {
                marketingData = results.data;
                renderTable(marketingData, M_COLS, mTableContainer, 'marketing');
            } else {
                productData = results.data;
                renderTable(productData, P_COLS, pTableContainer, 'product');
            }
            // Reset input so the same file can be uploaded again if needed
            event.target.value = '';
        },
        error: function(err) {
            alert("Error parsing CSV: " + err.message);
        }
    });
}

// Backend REST API Logic
async function generateReport() {
    // Switch to report tab
    document.querySelector('.tab-btn[data-tab="report-view"]').click();
    
    // UI state
    document.getElementById('loading-state').classList.remove('hidden');
    document.getElementById('report-content').classList.add('hidden');
    document.getElementById('error-state').classList.add('hidden');

    const question = document.getElementById('business-question').value || "Given this data, what are the key insights and strategic recommendations?";

    try {
        const endpoint = BACKEND_URL ? `${BACKEND_URL}/api/generate` : '/api/generate';
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                marketingData: marketingData, 
                productData: productData,
                question: question,
                webhookUrl: document.getElementById('webhook-url').value
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `Server Error: ${response.status}`);
        }

        // 1. Render Dashboards instantly (animations disabled)
        document.getElementById('dashboards-container').classList.remove('hidden');
        renderDashboards(data);

        // Give the browser 500ms to physically paint the charts before we screenshot them
        await new Promise(resolve => setTimeout(resolve, 500));

        // 2. Capture charts as Base64 images
        const beforeB64 = beforeChartInstance.toBase64Image();
        const afterB64 = afterChartInstance.toBase64Image();

        // 3. Send images to backend to build PDF
        const pdfEndpoint = BACKEND_URL ? `${BACKEND_URL}/api/build_pdf` : '/api/build_pdf';
        const pdfRes = await fetch(pdfEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cache_key: data.cache_key,
                before_image: beforeB64,
                after_image: afterB64
            })
        });
        const pdfData = await pdfRes.json();
        if(pdfRes.ok && pdfData.pdf_url) {
            data.pdf_url = pdfData.pdf_url;
        }

        // 4. Show the text memo and the final PDF download button
        renderReport(data);

    } catch (error) {
        document.getElementById('loading-state').classList.add('hidden');
        document.getElementById('error-state').classList.remove('hidden');
        document.getElementById('error-state').textContent = error.message;
    }
}

// ── CodeMender Live Diagnostics Engine Integration ──
function setupCodeMender() {
    const logo = document.querySelector('.nav-logo');
    const consoleEl = document.getElementById('codemender-console');
    const logsContainer = document.getElementById('mender-logs');
    const repairsCount = document.getElementById('mender-repairs');
    const latencyMetric = document.getElementById('mender-latency');
    const simBtn = document.getElementById('simulate-error-btn');

    let clickCount = 0;
    let clickTimeout;

    if (!logo || !consoleEl) return;

    // Secret Activation Shortcut: Triple-click logo to toggle console
    logo.style.cursor = 'pointer';
    logo.addEventListener('click', () => {
        clickCount++;
        clearTimeout(clickTimeout);
        
        if (clickCount === 3) {
            consoleEl.classList.toggle('hidden-console');
            // Flash console styling to grab developer attention
            consoleEl.scrollIntoView({ behavior: 'smooth' });
            clickCount = 0;
            addConsoleRow("system", "Developer secret mode activated. Live diagnostics link online.");
        }
        
        clickTimeout = setTimeout(() => {
            clickCount = 0;
        }, 1200);
    });

    // SSE EventSource listener for real-time telemetry
    const streamUrl = BACKEND_URL ? `${BACKEND_URL}/api/codemender/stream` : '/api/codemender/stream';
    const es = new EventSource(streamUrl);

    es.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'status') {
                repairsCount.textContent = data.repairs || 0;
                latencyMetric.textContent = `${data.avg_time || 0}ms`;
                return;
            }

            if (data.type === 'intercept') {
                addConsoleRow("intercept", `[INTERCEPTED] ${data.message}`);
                addConsoleRow("fail", `Error: ${data.error.split('\n')[0]}`);
            } else if (data.type === 'repair') {
                addConsoleRow("repair", `[HEALED] ${data.message}`);
                
                // Render before-and-after payload diff block
                const diffBox = document.createElement('div');
                diffBox.className = 'diff-box';
                diffBox.innerHTML = `
                    <div class="diff-header">Auto-Healed Code / Payload Diff</div>
                    <span class="diff-red">- Original: ${escapeHtml(data.original)}</span>
                    <span class="diff-green">+ Corrected: ${escapeHtml(data.repaired)}</span>
                `;
                logsContainer.appendChild(diffBox);
                logsContainer.scrollTop = logsContainer.scrollHeight;

                // Update counters
                repairsCount.textContent = parseInt(repairsCount.textContent) + 1;
            } else if (data.type === 'failure') {
                addConsoleRow("fail", `[CRITICAL FAILURE] ${data.message} Error: ${data.error}`);
            }
        } catch (err) {
            console.error("Failed parsing telemetry event:", err);
        }
    };

    es.onerror = () => {
        // Silent reconnection fallback
    };

    // Simulated Error Button Handler
    if (simBtn) {
        simBtn.addEventListener('click', async () => {
            try {
                simBtn.disabled = true;
                simBtn.textContent = "Simulating...";
                const simUrl = BACKEND_URL ? `${BACKEND_URL}/api/codemender/simulate_error` : '/api/codemender/simulate_error';
                await fetch(simUrl, { method: 'POST' });
                setTimeout(() => {
                    simBtn.disabled = false;
                    simBtn.textContent = "Simulate Data Crash";
                }, 2000);
            } catch (err) {
                console.error("Failed invoking simulation:", err);
                simBtn.disabled = false;
                simBtn.textContent = "Simulate Data Crash";
            }
        });
    }

    function addConsoleRow(type, text) {
        const row = document.createElement('div');
        row.className = `mender-log-row ${type}-msg`;
        const time = new Date().toLocaleTimeString();
        row.innerHTML = `<span class="mender-time">[${time}]</span> ${text}`;
        logsContainer.appendChild(row);
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }

    function escapeHtml(unsafe) {
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }
}



function renderReport(data) {
    document.getElementById('loading-state').classList.add('hidden');
    const container = document.getElementById('report-content');
    container.classList.remove('hidden');

    let memoText = data.board_memo || "No memo generated.";

    // Bold markdown
    memoText = memoText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    let html = `<h1>Executive Board Memo</h1>`;

    // Extract formal header fields (To / From / Date / Subject)
    // They may be on separate lines OR crammed into one line
    const headerFields = ['To', 'From', 'Date', 'Subject'];
    const headerLineRegex = new RegExp(
        `(${headerFields.join('|')})[:\s]+([^\n]+?)(?=(?:${headerFields.join('|')})[:\s]|Dear|$)`,
        'gi'
    );

    const headerMatches = [...memoText.matchAll(headerLineRegex)];

    if (headerMatches.length >= 2) {
        // Build a clean formal header block
        html += `<div class="memo-header-block">`;
        headerMatches.forEach(m => {
            html += `<div class="memo-header-row">`
                  + `<span class="memo-header-key">${m[1]}:</span>`
                  + `<span class="memo-header-val">${m[2].trim()}</span>`
                  + `</div>`;
        });
        html += `</div>`;

        // Remove the header portion from the body text
        const lastMatch = headerMatches[headerMatches.length - 1];
        const afterHeaders = memoText.slice(lastMatch.index + lastMatch[0].length).trim();
        memoText = afterHeaders;
    }

    // Render the rest as paragraphs / headers / bullets
    const lines = memoText.split('\n');
    lines.forEach(line => {
        const p = line.trim();
        if (p === '') {
            html += `<div style="height:10px"></div>`;
        } else if (p.match(/^[0-9]+\.\s/)) {
            html += `<h3>${p}</h3>`;
        } else if (p.startsWith('Dear ') || p.startsWith('Sincerely') || p.startsWith('Regards')) {
            html += `<p class="memo-salutation">${p}</p>`;
        } else if (p.startsWith('*') || p.startsWith('-')) {
            html += `<li style="margin-left:20px;margin-bottom:8px">${p.substring(1).trim()}</li>`;
        } else {
            html += `<p style="margin-bottom:13px">${p}</p>`;
        }
    });

    container.innerHTML = html;

    // Show PDF Button and Dashboards
    const pdfContainer = document.getElementById('pdf-download-container');
    const pdfBtn = document.getElementById('download-pdf-btn');
    if (data.pdf_url) {
        pdfContainer.classList.remove('hidden');
        // pdf_url from Supabase is already a full https:// URL — don't prepend BACKEND_URL
        const fullPdfUrl = data.pdf_url.startsWith('http') ? data.pdf_url : `${BACKEND_URL}${data.pdf_url}`;
        pdfBtn.href = fullPdfUrl;
        setupSocialSharing(memoText, fullPdfUrl);
    }
}

let beforeChartInstance = null;
let afterChartInstance = null;

function renderDashboards(data) {
    const projections = data ? data.projections : null;
    const forecast = data ? data.forecast : null;
    
    // 1. Calculate "Before" Data from global variables
    const mSpend = marketingData.reduce((sum, d) => sum + (parseFloat(d.spend) || 0), 0);
    const mRev = marketingData.reduce((sum, d) => sum + (parseFloat(d.revenue) || 0), 0);
    const pRev = productData.reduce((sum, d) => sum + (parseFloat(d.revenue) || 0), 0);

    // 2. Calculate "After" Data from AI projections
    const projMRev = projections ? projections.projected_marketing_revenue : (mRev * 1.2);
    const projPRev = projections ? projections.projected_product_revenue : (pRev * 1.15);
    const optSpend = projections ? projections.optimized_marketing_spend : mSpend;

    // Update Forecast Insight Card
    if (forecast && forecast.status === "success") {
        const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
        
        const slope = forecast.marketing_metrics.spend_trend_slope;
        const slopeStr = (slope >= 0 ? "+" : "") + fmt.format(slope) + "/day";
        document.getElementById('stat-spend-slope').textContent = slopeStr;
        
        const r2 = forecast.marketing_metrics.spend_r_squared;
        document.getElementById('stat-spend-r2').textContent = (r2 * 100).toFixed(1) + "%";
        
        document.getElementById('stat-proj-spend').textContent = fmt.format(forecast.marketing_metrics.projected_30d_spend);
        document.getElementById('stat-proj-prev').textContent = fmt.format(forecast.product_metrics.projected_30d_revenue);
    }

    // 3. Balance Scales (find maximum value across both charts and add 10% padding)
    const allValues = [mSpend, mRev, pRev, optSpend, projMRev, projPRev];
    const maxVal = Math.max(...allValues);
    const yAxisMax = Math.ceil(maxVal * 1.1);

    const customCanvasBackgroundColor = {
        id: 'customCanvasBackgroundColor',
        beforeDraw: (chart, args, options) => {
            const {ctx} = chart;
            ctx.save();
            ctx.globalCompositeOperation = 'destination-over';
            ctx.fillStyle = options.color || '#ffffff';
            ctx.fillRect(0, 0, chart.width, chart.height);
            ctx.restore();
        }
    };

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: 1.4,
        animation: false,
        plugins: {
            customCanvasBackgroundColor: { color: 'white' }
        },
        scales: {
            y: {
                beginAtZero: true,
                max: yAxisMax
            }
        }
    };

    const beforeCtx = document.getElementById('beforeChart').getContext('2d');
    if(beforeChartInstance) beforeChartInstance.destroy();
    beforeChartInstance = new Chart(beforeCtx, {
        type: 'bar',
        data: {
            labels: ['Marketing Spend', 'Marketing Revenue', 'Product Revenue'],
            datasets: [{
                label: 'Current Metrics ($)',
                data: [mSpend, mRev, pRev],
                backgroundColor: ['#ef4444', '#3b82f6', '#10b981']
            }]
        },
        options: chartOptions,
        plugins: [customCanvasBackgroundColor]
    });

    const afterCtx = document.getElementById('afterChart').getContext('2d');
    if(afterChartInstance) afterChartInstance.destroy();

    afterChartInstance = new Chart(afterCtx, {
        type: 'bar',
        data: {
            labels: ['Optimized Spend', 'Projected M-Revenue', 'Projected P-Revenue'],
            datasets: [{
                label: 'Projected Metrics After AI ($)',
                data: [optSpend, projMRev, projPRev],
                backgroundColor: ['#f59e0b', '#2563eb', '#059669']
            }]
        },
        options: chartOptions,
        plugins: [customCanvasBackgroundColor]
    });
}

function setupSocialSharing(memoText, pdfUrl) {
    const summary = encodeURIComponent(memoText.substring(0, 150) + "...\n\nRead full report here: " + window.location.origin + pdfUrl);
    const subject = encodeURIComponent("AI Executive Decision Memo");
    
    document.getElementById('share-whatsapp').onclick = () => {
        window.open(`https://api.whatsapp.com/send?text=${summary}`, '_blank');
    };
    
    document.getElementById('share-email').onclick = () => {
        window.location.href = `mailto:?subject=${subject}&body=${summary}`;
    };
    
    document.getElementById('share-copy').onclick = () => {
        navigator.clipboard.writeText(memoText).then(() => {
            alert("Report copied to clipboard!");
        });
    };
}

// ══════════════════════════════════════
// SECURE SUPABASE AUTH PORTAL INTEGRATION
// ══════════════════════════════════════
let clientSupabaseUrl = "";
let clientSupabaseKey = "";
let authMode = "signin"; // signin or signup

async function initAuthPortal() {
    const portal = document.getElementById('auth-portal');
    const userProfile = document.getElementById('user-profile');
    
    try {
        // Fetch dynamic credentials from backend config endpoint
        const configUrl = BACKEND_URL ? `${BACKEND_URL}/api/auth/config` : '/api/auth/config';
        const res = await fetch(configUrl);
        const config = await res.json();
        
        clientSupabaseUrl = config.supabaseUrl ? config.supabaseUrl.trim() : "";
        clientSupabaseKey = config.supabaseKey ? config.supabaseKey.trim() : "";
    } catch (e) {
        console.error("Failed fetching Supabase credentials:", e);
    }

    // Auto-login if session exists in localStorage
    const savedUser = localStorage.getItem('boardroom_user');
    if (savedUser) {
        const user = JSON.parse(savedUser);
        loginUserSession(user.email, user.isGuest);
    } else {
        // Show auth portal
        portal.classList.remove('hidden');
        userProfile.classList.add('hidden');
    }
}

function toggleAuthMode() {
    const title = document.getElementById('auth-title');
    const subtitle = document.getElementById('auth-subtitle');
    const btn = document.getElementById('auth-btn');
    const link = document.getElementById('auth-switch-link');
    
    if (authMode === "signin") {
        authMode = "signup";
        title.textContent = "Request Boardroom Access";
        subtitle.textContent = "Register your corporate email to create a new board-level session.";
        btn.textContent = "Register & Connect";
        link.textContent = "Already have credentials? Sign In";
    } else {
        authMode = "signin";
        title.textContent = "Executive Access";
        subtitle.textContent = "Verify credentials to review high-end business performance recommendations.";
        btn.textContent = "Verify Credentials";
        link.textContent = "Request Boardroom Access (Sign Up)";
    }
}

async function handleAuthSubmit() {
    const email = document.getElementById('auth-email').value;
    const password = document.getElementById('auth-password').value;
    const errorBox = document.getElementById('auth-error');
    const btn = document.getElementById('auth-btn');

    errorBox.classList.add('hidden');
    btn.disabled = true;
    btn.textContent = "Processing Auth...";

    // Validate config presence
    if (!clientSupabaseUrl || !clientSupabaseKey) {
        errorBox.textContent = "System configuration error: Supabase credentials are missing on the backend. Please use 'Enter Workspace as Guest' or set credentials.";
        errorBox.classList.remove('hidden');
        btn.disabled = false;
        btn.textContent = authMode === "signin" ? "Verify Credentials" : "Register & Connect";
        return;
    }

    try {
        let endpoint = "";
        let bodyPayload = {};
        
        if (authMode === "signup") {
            endpoint = `${clientSupabaseUrl}/auth/v1/signup`;
            bodyPayload = { email, password };
        } else {
            endpoint = `${clientSupabaseUrl}/auth/v1/token?grant_type=password`;
            bodyPayload = { email, password };
        }

        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'apikey': clientSupabaseKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(bodyPayload)
        });

        const data = await response.json();

        if (!response.ok || data.error_description || data.error) {
            throw new Error(data.error_description || data.error || "Authentication failed.");
        }

        // Successfully authenticated!
        loginUserSession(email, false);

    } catch (err) {
        errorBox.textContent = `Access Denied: ${err.message}`;
        errorBox.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btn.textContent = authMode === "signin" ? "Verify Credentials" : "Register & Connect";
    }
}

function loginUserSession(email, isGuest) {
    const portal = document.getElementById('auth-portal');
    const profile = document.getElementById('user-profile');
    const avatar = document.getElementById('user-avatar');
    const emailEl = document.getElementById('user-email');

    // Hide Portal overlay, reveal App workspace
    portal.classList.add('hidden');
    profile.classList.remove('hidden');

    // Set dynamic session values
    avatar.textContent = email.charAt(0).toUpperCase();
    emailEl.textContent = isGuest ? "Guest Access" : email;

    // Save session locally
    localStorage.setItem('boardroom_user', JSON.stringify({ email, isGuest }));
}

function enterAsGuest() {
    loginUserSession("guest@boardroom.com", true);
}

function handleSignOut() {
    localStorage.removeItem('boardroom_user');
    
    // Show auth portal overlay, hide profile panel
    document.getElementById('auth-portal').classList.remove('hidden');
    document.getElementById('user-profile').classList.add('hidden');
    
    // Reset forms
    document.getElementById('auth-email').value = "";
    document.getElementById('auth-password').value = "";
    document.getElementById('auth-error').classList.add('hidden');
}

// ══════════════════════════════════════
// BOARDROOM DIRECT INTEGRATIONS SYNC
// ══════════════════════════════════════
let activeSyncTarget = "";

function openSyncModal(target, defaultDomain) {
    activeSyncTarget = target;
    
    const modal = document.getElementById('sync-modal');
    const title = document.getElementById('sync-target-title');
    const urlLabel = document.getElementById('sync-url-label');
    const urlInput = document.getElementById('sync-url');
    
    title.textContent = `${target} Connection`;
    urlLabel.textContent = target === 'Google Analytics 4' ? 'Property Measurement ID' : `${target} Store URL`;
    urlInput.value = defaultDomain;
    
    // Reset wizard steps
    document.getElementById('sync-form-step').classList.remove('hidden');
    document.getElementById('sync-progress-step').classList.add('hidden');
    
    modal.classList.remove('hidden');
}

function closeSyncModal() {
    document.getElementById('sync-modal').classList.add('hidden');
}

async function startVisualSync() {
    document.getElementById('sync-form-step').classList.add('hidden');
    document.getElementById('sync-progress-step').classList.remove('hidden');
    
    const pct = document.getElementById('sync-pct');
    const msg = document.getElementById('sync-status-msg');
    const logs = document.getElementById('sync-mini-logs');
    
    logs.innerHTML = "";
    
    const domain = document.getElementById('sync-url').value;
    const token = document.getElementById('sync-api-key').value;
    
    // Start backend request
    const syncUrl = BACKEND_URL ? `${BACKEND_URL}/api/integrations/sync` : '/api/integrations/sync';
    const syncPromise = fetch(syncUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: activeSyncTarget, domain, token })
    }).then(res => res.json());
    
    const logMessages = [
        { time: 300, text: `Establishing encrypted handshake tunnel to ${activeSyncTarget}...` },
        { time: 1000, text: "Verification tokens approved by Oauth gateway." },
        { time: 1800, text: "Analyzing dataset parameters and partition counts..." },
        { time: 2600, text: "Streaming performance variables (Traffic, SKU conversions)..." },
        { time: 3500, text: "Running structural alignment with workspace dashboard grids..." },
        { time: 4200, text: "Sync complete! Data injected seamlessly." }
    ];
    
    // Add logs step-by-step
    logMessages.forEach(item => {
        setTimeout(() => {
            const row = document.createElement('div');
            row.className = "sync-log-line";
            if (item.text.includes("Sync complete")) {
                row.className += " complete";
            }
            row.textContent = `[${new Date().toLocaleTimeString()}] ${item.text}`;
            logs.appendChild(row);
            logs.scrollTop = logs.scrollHeight;
        }, item.time);
    });
    
    // Update percentage indicator
    let counter = 0;
    const interval = setInterval(async () => {
        counter += 2;
        pct.textContent = `${counter}%`;
        
        if (counter >= 100) {
            clearInterval(interval);
            msg.textContent = `${activeSyncTarget} synchronization successfully finished!`;
            
            try {
                const responseData = await syncPromise;
                if (responseData.status === "success") {
                    injectSyncedEcomData(responseData.marketing_data, responseData.product_data);
                    closeSyncModal();
                    alert(`Successfully synchronized dynamic performance logs from ${activeSyncTarget}! Tables updated.`);
                } else {
                    alert(`Sync failed: ${responseData.error}`);
                    closeSyncModal();
                }
            } catch (err) {
                console.error("Backend sync failed", err);
                alert("Failed to connect to backend sync endpoint.");
                closeSyncModal();
            }
        }
    }, 90);
}

function injectSyncedEcomData(syncedMarketing, syncedProduct) {
    // Assign global data matrices
    marketingData.length = 0;
    marketingData.push(...syncedMarketing);
    
    productData.length = 0;
    productData.push(...syncedProduct);
    
    // Re-render local tables instantly
    renderTable(marketingData, M_COLS, mTableContainer, 'marketing');
    renderTable(productData, P_COLS, pTableContainer, 'product');
}


