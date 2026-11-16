/**
 * Inventory Management Module JavaScript
 * Handles CRUD operations, stock movements, modal interactions, and filtering.
 */

let searchTimeout = null;
let currentProducts = [];

document.addEventListener('DOMContentLoaded', () => {
    fetchProducts();
});

function debounceSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(fetchProducts, 300);
}

async function fetchProducts() {
    const search = document.getElementById('inventorySearch')?.value || '';
    const category = document.getElementById('categoryFilter')?.value || 'All';
    const status = document.getElementById('statusFilter')?.value || '';

    const url = `/api/products?search=${encodeURIComponent(search)}&category=${encodeURIComponent(category)}&status=${encodeURIComponent(status)}`;
    const tbody = document.getElementById('productsTableBody');

    try {
        const res = await fetch(url);
        const data = await res.json();

        if (!data.success) {
            tbody.innerHTML = `<tr><td colspan="10" class="text-center text-danger py-4">Error: ${data.error}</td></tr>`;
            return;
        }

        currentProducts = data.products || [];
        document.getElementById('productCountBadge').textContent = currentProducts.length;

        // Populate category dropdown if not populated
        const catSelect = document.getElementById('categoryFilter');
        if (catSelect && catSelect.options.length <= 1 && data.categories) {
            data.categories.forEach(cat => {
                const opt = document.createElement('option');
                opt.value = cat;
                opt.textContent = cat;
                catSelect.appendChild(opt);
            });
        }

        renderProductsTable(currentProducts);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="10" class="text-center text-danger py-4">Failed to fetch products: ${err.message}</td></tr>`;
    }
}

function renderProductsTable(products) {
    const tbody = document.getElementById('productsTableBody');
    if (!products.length) {
        tbody.innerHTML = `<tr><td colspan="10" class="text-center py-4 text-muted">No products match your search or filter criteria.</td></tr>`;
        return;
    }

    tbody.innerHTML = products.map(p => {
        let statusBadge = '<span class="badge badge-healthy">HEALTHY</span>';
        if (p.quantity === 0) {
            statusBadge = '<span class="badge badge-critical">OUT OF STOCK</span>';
        } else if (p.quantity <= p.reorder_threshold) {
            statusBadge = '<span class="badge badge-high">LOW STOCK</span>';
        }

        const totalValue = (p.quantity * p.unit_price).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});

        return `
            <tr>
                <td><code>${p.product_id}</code></td>
                <td>
                    <a href="javascript:void(0)" onclick="viewProductDetail('${p.product_id}')" class="fw-semibold text-dark text-decoration-none">
                        ${p.product_name}
                    </a>
                </td>
                <td><span class="badge bg-light text-dark border">${p.category}</span></td>
                <td class="fw-bold ${p.quantity === 0 ? 'text-danger' : (p.quantity <= p.reorder_threshold ? 'text-warning' : 'text-dark')}">
                    ${p.quantity} <small class="text-muted fw-normal">/ min ${p.reorder_threshold}</small>
                </td>
                <td>₹${p.unit_price.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                <td class="fw-semibold">₹${totalValue}</td>
                <td class="small text-muted"><i class="bi bi-geo-alt me-1"></i>${p.warehouse_location}</td>
                <td class="small">${p.supplier}</td>
                <td>${statusBadge}</td>
                <td class="text-end">
                    ${(window.USER_ROLE === 'Administrator') ? `
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-teal btn-sm text-teal-600" title="Record Movement" onclick="openMovementModal('${p.product_id}', '${escapeQuotes(p.product_name)}', ${p.quantity})">
                                <i class="bi bi-arrow-left-right"></i>
                            </button>
                            <button class="btn btn-outline-secondary btn-sm" title="Edit Product" onclick="openEditProductModal('${p.product_id}')">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-outline-danger btn-sm" title="Delete Product" onclick="confirmDeleteProduct('${p.product_id}', '${escapeQuotes(p.product_name)}')">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    ` : `
                        <button class="btn btn-outline-secondary btn-sm" title="View Details" onclick="viewProductDetail('${p.product_id}')">
                            <i class="bi bi-eye me-1"></i> Details
                        </button>
                    `}
                </td>
            </tr>
        `;
    }).join('');
}

function escapeQuotes(str) {
    return (str || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ---------------- Add Product ----------------
async function submitAddProduct(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());

    try {
        const res = await fetch('/api/products', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (result.success) {
            bootstrap.Modal.getInstance(document.getElementById('addProductModal')).hide();
            form.reset();
            fetchProducts();
            showToast('Success', result.message, 'success');
        } else {
            alert('Error adding product: ' + result.error);
        }
    } catch (err) {
        alert('Network error: ' + err.message);
    }
}

// ---------------- Edit Product ----------------
function openEditProductModal(productId) {
    const p = currentProducts.find(x => x.product_id === productId);
    if (!p) return;

    document.getElementById('edit_product_id').value = p.product_id;
    document.getElementById('edit_product_id_display').value = p.product_id;
    document.getElementById('edit_product_name').value = p.product_name;
    document.getElementById('edit_category').value = p.category;
    document.getElementById('edit_quantity').value = p.quantity;
    document.getElementById('edit_unit_price').value = p.unit_price;
    document.getElementById('edit_supplier').value = p.supplier;
    document.getElementById('edit_warehouse_location').value = p.warehouse_location;
    document.getElementById('edit_reorder_threshold').value = p.reorder_threshold;

    new bootstrap.Modal(document.getElementById('editProductModal')).show();
}

async function submitEditProduct(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());
    const productId = payload.product_id;

    try {
        const res = await fetch(`/api/products/${productId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (result.success) {
            bootstrap.Modal.getInstance(document.getElementById('editProductModal')).hide();
            fetchProducts();
            showToast('Success', result.message, 'success');
        } else {
            alert('Error updating product: ' + result.error);
        }
    } catch (err) {
        alert('Network error: ' + err.message);
    }
}

// ---------------- Delete Product ----------------
async function confirmDeleteProduct(productId, productName) {
    if (!confirm(`Are you sure you want to delete product ${productId} (${productName}) and all associated movement history?`)) {
        return;
    }

    try {
        const res = await fetch(`/api/products/${productId}`, { method: 'DELETE' });
        const result = await res.json();
        if (result.success) {
            fetchProducts();
            showToast('Deleted', result.message, 'info');
        } else {
            alert('Error deleting product: ' + result.error);
        }
    } catch (err) {
        alert('Network error: ' + err.message);
    }
}

// ---------------- Stock Movement ----------------
function openMovementModal(productId, productName, currentQty) {
    document.getElementById('movement_product_id').value = productId;
    document.getElementById('movement_product_display').textContent = `${productId} - ${productName}`;
    document.getElementById('movement_available_display').textContent = currentQty;
    document.getElementById('movementForm').reset();
    document.getElementById('movement_product_id').value = productId;

    new bootstrap.Modal(document.getElementById('movementModal')).show();
}

async function submitMovement(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());

    try {
        const res = await fetch('/api/transactions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (result.success) {
            bootstrap.Modal.getInstance(document.getElementById('movementModal')).hide();
            fetchProducts();
            showToast('Movement Recorded', result.message, 'success');
        } else {
            alert('Movement rejected: ' + result.error);
        }
    } catch (err) {
        alert('Network error: ' + err.message);
    }
}

// ---------------- Product Details & History ----------------
async function viewProductDetail(productId) {
    const modalEl = document.getElementById('productDetailModal');
    const contentEl = document.getElementById('productDetailContent');
    contentEl.innerHTML = '<div class="text-center py-4 text-muted"><i class="bi bi-arrow-repeat spin"></i> Loading details...</div>';
    new bootstrap.Modal(modalEl).show();

    try {
        const res = await fetch(`/api/products/${productId}`);
        const result = await res.json();

        if (!result.success) {
            contentEl.innerHTML = `<div class="alert alert-danger">${result.error}</div>`;
            return;
        }

        const p = result.product;
        const txs = result.transactions || [];
        const totalVal = (p.quantity * p.unit_price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});

        contentEl.innerHTML = `
            <div class="row g-3 mb-4">
                <div class="col-md-6">
                    <div class="border rounded p-3 bg-light">
                        <h6 class="fw-bold text-navy-900 mb-2">${p.product_name}</h6>
                        <div class="small text-muted mb-1">SKU: <code>${p.product_id}</code></div>
                        <div class="small text-muted mb-1">Category: <strong>${p.category}</strong></div>
                        <div class="small text-muted">Supplier: <strong>${p.supplier}</strong></div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="border rounded p-3 bg-light">
                        <div class="d-flex justify-content-between mb-1">
                            <span class="small text-muted">Available Stock:</span>
                            <strong class="fs-5 ${p.quantity === 0 ? 'text-danger' : (p.quantity <= p.reorder_threshold ? 'text-warning' : 'text-success')}">${p.quantity} units</strong>
                        </div>
                        <div class="d-flex justify-content-between mb-1">
                            <span class="small text-muted">Unit Price:</span>
                            <span>₹${p.unit_price.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                        </div>
                        <div class="d-flex justify-content-between mb-1">
                            <span class="small text-muted">Holding Value:</span>
                            <span class="fw-bold text-dark">₹${totalVal}</span>
                        </div>
                        <div class="d-flex justify-content-between">
                            <span class="small text-muted">Location:</span>
                            <span class="badge bg-secondary">${p.warehouse_location}</span>
                        </div>
                    </div>
                </div>
            </div>

            <h6 class="fw-bold text-navy-900 mb-2"><i class="bi bi-clock-history me-1"></i> Transaction Ledger (Recent ${txs.length})</h6>
            <div class="table-responsive" style="max-height: 250px;">
                <table class="table table-sm table-custom align-middle">
                    <thead>
                        <tr>
                            <th>Ref</th>
                            <th>Type</th>
                            <th>Quantity</th>
                            <th>Date</th>
                            <th>Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${txs.length ? txs.map(t => `
                            <tr>
                                <td><code>${t.reference_no || ('TX-' + t.id)}</code></td>
                                <td><span class="badge ${t.transaction_type === 'INCOMING' ? 'badge-healthy' : 'badge-moderate'}">${t.transaction_type}</span></td>
                                <td class="fw-bold">${t.quantity}</td>
                                <td class="small text-muted">${t.transaction_date}</td>
                                <td class="small text-muted">${t.notes || '-'}</td>
                            </tr>
                        `).join('') : '<tr><td colspan="5" class="text-center py-2 text-muted">No transactions recorded yet.</td></tr>'}
                    </tbody>
                </table>
            </div>
        `;
    } catch (err) {
        contentEl.innerHTML = `<div class="alert alert-danger">Error: ${err.message}</div>`;
    }
}

function showToast(title, message, type) {
    // Basic notification feedback
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} position-fixed bottom-0 end-0 m-3 shadow-lg fade show`;
    toast.style.zIndex = '9999';
    toast.innerHTML = `<strong>${title}:</strong> ${message}`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}
