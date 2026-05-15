// Configuration
// IMPORTANT: Change this to your live Render.com URL once the backend is deployed!
// Example: "https://kpi-intelligence-reporter.onrender.com"
// If you leave it empty (""), it will use the same host (for local testing).
const BACKEND_URL = "";

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
                question: question
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `Server Error: ${response.status}`);
        }

        // 1. Render Dashboards instantly (animations disabled)
        document.getElementById('dashboards-container').classList.remove('hidden');
        renderDashboards(data.projections);

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



function renderReport(data) {
    document.getElementById('loading-state').classList.add('hidden');
    const container = document.getElementById('report-content');
    container.classList.remove('hidden');

    let memoText = data.board_memo || "No memo generated.";
    
    // Simple parsing for bold markdown
    memoText = memoText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    let html = `<h1>Executive Board Memo</h1>`;
    
    // Split by newlines and create paragraphs/headers
    const paragraphs = memoText.split('\n');
    paragraphs.forEach(p => {
        if(p.trim() === '') return;
        if(p.match(/^[0-9]\.\s/)) {
            // It's a numbered section header like "1. Context"
            html += `<h3>${p}</h3>`;
        } else if(p.startsWith('*') || p.startsWith('-')) {
            html += `<li style="margin-left:20px; margin-bottom: 8px;">${p.substring(1).trim()}</li>`;
        } else {
            html += `<p style="margin-bottom: 12px;">${p}</p>`;
        }
    });

    container.innerHTML = html;

    // Show PDF Button and Dashboards
    const pdfContainer = document.getElementById('pdf-download-container');
    const pdfBtn = document.getElementById('download-pdf-btn');
    if (data.pdf_url) {
        pdfContainer.classList.remove('hidden');
        const fullPdfUrl = BACKEND_URL ? `${BACKEND_URL}${data.pdf_url}` : data.pdf_url;
        pdfBtn.href = fullPdfUrl;
        setupSocialSharing(memoText, fullPdfUrl);
    }
}

let beforeChartInstance = null;
let afterChartInstance = null;

function renderDashboards(projections) {
    // 1. Calculate "Before" Data from global variables
    const mSpend = marketingData.reduce((sum, d) => sum + (parseFloat(d.spend) || 0), 0);
    const mRev = marketingData.reduce((sum, d) => sum + (parseFloat(d.revenue) || 0), 0);
    const pRev = productData.reduce((sum, d) => sum + (parseFloat(d.revenue) || 0), 0);

    // 2. Calculate "After" Data from AI projections
    const projMRev = projections ? projections.projected_marketing_revenue : (mRev * 1.2);
    const projPRev = projections ? projections.projected_product_revenue : (pRev * 1.15);
    const optSpend = projections ? projections.optimized_marketing_spend : mSpend;

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
