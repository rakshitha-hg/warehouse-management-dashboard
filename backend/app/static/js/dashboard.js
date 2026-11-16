/**
 * Dashboard Analytics and Visualization Manager
 * Connects to Apache Spark backend API and manages interactive Chart.js charts.
 */

let monthlyMovementChart = null;
let categoryDistributionChart = null;
let topSellingChart = null;

// Palette: Navy, Teal, Sky, Emerald, Amber, Purple
const THEME_COLORS = [
    '#0d9488', // Teal
    '#0f172a', // Navy
    '#0ea5e9', // Sky Blue
    '#10b981', // Emerald
    '#f59e0b', // Amber
    '#6366f1', // Indigo
    '#ec4899', // Pink
    '#8b5cf6'  // Purple
];

document.addEventListener('DOMContentLoaded', () => {
    loadDashboardAnalytics();
    loadRecentTransactions();
});

async function loadDashboardAnalytics() {
    try {
        const response = await fetch('/api/analytics/dashboard');
        const result = await response.json();

        if (!result.success) {
            console.error('Spark analytics error:', result.error);
            return;
        }

        const data = result.data;
        const summary = data.summary;
        const sparkInfo = result.spark;

        // 1. Update Spark Diagnostics Banner
        if (sparkInfo) {
            const latencyEl = document.getElementById('spark-latency');
            const tsEl = document.getElementById('spark-timestamp');
            if (latencyEl) latencyEl.textContent = `${sparkInfo.last_execution_ms || data.spark_execution_time_ms || 120} ms`;
            if (tsEl) tsEl.textContent = sparkInfo.last_processed_timestamp || data.processed_at || 'Just now';
        }

        // 2. Populate 8 KPI Metric Cards
        document.getElementById('stat-total-products').textContent = (summary.total_products || 0).toLocaleString();
        document.getElementById('stat-total-units').textContent = (summary.total_stock_units || 0).toLocaleString();
        document.getElementById('stat-inventory-val').textContent = `₹${(summary.total_inventory_value || 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        document.getElementById('stat-low-stock').textContent = (summary.low_stock_count || 0).toLocaleString();
        document.getElementById('stat-out-of-stock').textContent = (summary.out_of_stock_count || 0).toLocaleString();
        document.getElementById('stat-incoming-units').textContent = (summary.total_incoming_units || 0).toLocaleString();
        document.getElementById('stat-outgoing-units').textContent = (summary.total_outgoing_units || 0).toLocaleString();
        document.getElementById('stat-outgoing-val').textContent = `₹${(summary.total_outgoing_val || 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;

        // 3. Render Monthly Movement Chart
        renderMonthlyMovementChart(data.monthly_trends || []);

        // 4. Render Category Distribution Chart
        renderCategoryDistributionChart(data.categories || []);

        // 5. Render Top Selling Products Chart
        renderTopSellingChart(data.top_selling || []);

        // 6. Populate Low Stock Table
        populateLowStockTable(data.low_stock_analysis || []);

    } catch (err) {
        console.error('Failed to load dashboard data:', err);
    }
}

function renderMonthlyMovementChart(trends) {
    const ctx = document.getElementById('monthlyMovementChart');
    if (!ctx) return;

    const labels = trends.map(t => t.period);
    const incomingData = trends.map(t => t.incoming);
    const outgoingData = trends.map(t => t.outgoing);

    if (monthlyMovementChart) {
        monthlyMovementChart.destroy();
    }

    monthlyMovementChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels.length ? labels : ['Recent Period'],
            datasets: [
                {
                    label: 'Incoming Stock (Units)',
                    data: incomingData.length ? incomingData : [0],
                    backgroundColor: '#0ea5e9',
                    borderRadius: 5,
                    borderSkipped: false
                },
                {
                    label: 'Outgoing Dispatches (Units)',
                    data: outgoingData.length ? outgoingData : [0],
                    backgroundColor: '#0d9488',
                    borderRadius: 5,
                    borderSkipped: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { font: { family: 'Inter', size: 12 }, boxWidth: 14 }
                },
                tooltip: {
                    padding: 10,
                    cornerRadius: 6
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { font: { family: 'Inter', size: 11 } }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: '#f1f5f9' },
                    ticks: { font: { family: 'Inter', size: 11 } }
                }
            }
        }
    });
}

function renderCategoryDistributionChart(categories) {
    const ctx = document.getElementById('categoryDistributionChart');
    if (!ctx) return;

    const labels = categories.map(c => c.category);
    const values = categories.map(c => c.category_value);

    if (categoryDistributionChart) {
        categoryDistributionChart.destroy();
    }

    categoryDistributionChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: THEME_COLORS.slice(0, labels.length),
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '68%',
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        boxWidth: 12,
                        font: { family: 'Inter', size: 11 },
                        padding: 12
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const val = context.raw || 0;
                            return ` ${context.label}: ₹${val.toLocaleString('en-IN')}`;
                        }
                    }
                }
            }
        }
    });
}

function renderTopSellingChart(items) {
    const ctx = document.getElementById('topSellingChart');
    if (!ctx) return;

    const labels = items.map(i => i.product_name.length > 20 ? i.product_name.substring(0, 20) + '...' : i.product_name);
    const data = items.map(i => i.total_dispatched);

    if (topSellingChart) {
        topSellingChart.destroy();
    }

    topSellingChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Units Dispatched',
                data: data,
                backgroundColor: '#1e293b',
                hoverBackgroundColor: '#0d9488',
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        afterLabel: function(context) {
                            const item = items[context.dataIndex];
                            return `Revenue: ₹${(item.total_revenue || 0).toLocaleString('en-IN')}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    grid: { color: '#f1f5f9' },
                    ticks: { font: { family: 'Inter', size: 11 } }
                },
                y: {
                    grid: { display: false },
                    ticks: { font: { family: 'Inter', size: 11 } }
                }
            }
        }
    });
}

function populateLowStockTable(items) {
    const tbody = document.getElementById('lowStockTableBody');
    if (!tbody) return;

    if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center py-3 text-muted">All products have healthy inventory levels.</td></tr>';
        return;
    }

    tbody.innerHTML = items.map(item => `
        <tr>
            <td><code>${item.product_id}</code></td>
            <td class="fw-semibold">${item.product_name}</td>
            <td class="fw-bold ${item.quantity === 0 ? 'text-danger' : 'text-warning'}">${item.quantity}</td>
            <td>${item.reorder_threshold}</td>
            <td class="small text-muted">${item.warehouse_location}</td>
            <td>
                ${item.quantity === 0 
                    ? '<span class="badge badge-critical">OUT OF STOCK</span>' 
                    : '<span class="badge badge-high">LOW STOCK</span>'}
            </td>
        </tr>
    `).join('');
}

async function loadRecentTransactions() {
    try {
        const res = await fetch('/api/transactions?limit=7');
        const data = await res.json();
        const tbody = document.getElementById('recentTransactionsTableBody');
        if (!tbody) return;

        if (!data.success || !data.transactions.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4 text-muted">No warehouse transactions recorded.</td></tr>';
            return;
        }

        tbody.innerHTML = data.transactions.map(tx => {
            let badgeClass = 'bg-secondary';
            if (tx.transaction_type === 'INCOMING') badgeClass = 'badge-healthy';
            else if (tx.transaction_type === 'OUTGOING') badgeClass = 'badge-moderate';
            else if (tx.transaction_type === 'ADJUSTMENT') badgeClass = 'badge-high';

            const total = (tx.quantity * tx.unit_price).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});

            return `
                <tr>
                    <td><code>${tx.reference_no || ('TX-' + tx.id)}</code></td>
                    <td>
                        <div class="fw-semibold">${tx.product_name || tx.product_id}</div>
                        <small class="text-muted">${tx.product_id}</small>
                    </td>
                    <td><span class="badge ${badgeClass}">${tx.transaction_type}</span></td>
                    <td class="fw-bold">${tx.quantity}</td>
                    <td>₹${tx.unit_price.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                    <td class="fw-semibold text-dark">₹${total}</td>
                    <td class="small text-muted">${tx.transaction_date}</td>
                    <td class="small text-muted">${tx.notes || '-'}</td>
                </tr>
            `;
        }).join('');
    } catch (err) {
        console.error('Failed to load recent transactions:', err);
    }
}
