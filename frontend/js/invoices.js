/**
 * CRM Invoices Module
 * Handles invoice creation with multi-item calculation, billing history, and quick payments.
 */

let currentPage = 1;
let currentTotalPages = 1;
let cachedProducts = [];
let cachedCustomers = [];
let bulkSelection = null;
let currentViewInvoiceId = null;

function downloadInvoicePdf(id = null) {
  const invId = id || currentViewInvoiceId;
  if (!invId) return;
  const token = typeof ApiClient !== 'undefined' ? ApiClient.getToken() : '';
  window.open(`/api/export/invoices?format=pdf&invoice_id=${invId}&token=${token}`, '_blank');
}

document.addEventListener('DOMContentLoaded', async () => {
  const user = await Auth.requireAuth();
  if (!user) return;

  UI.updateNotificationBadge();
  setupEventListeners();
  await loadLookups();
  loadInvoices();
});

function setupEventListeners() {
  // Bulk selection setup
  bulkSelection = UI.initBulkSelection({
    selectAllId: 'selectAll',
    rowSelector: '.invoice-row-cb',
    toolbarId: 'bulkActionsToolbar',
    countId: 'bulkSelectedCount'
  });

  // Bulk Actions
  document.getElementById('bulkDeleteBtn')?.addEventListener('click', () => {
    const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
    UI.bulkDelete('invoices', ids, () => {
      if (bulkSelection) bulkSelection.clearSelection();
      loadInvoices();
    });
  });

  document.getElementById('bulkStatusBtn')?.addEventListener('click', () => {
    const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
    UI.bulkStatus('invoices', ids, [
      { value: 'draft', label: 'Draft' },
      { value: 'sent', label: 'Sent' },
      { value: 'paid', label: 'Paid' },
      { value: 'partially_paid', label: 'Partially Paid' },
      { value: 'overdue', label: 'Overdue' },
      { value: 'cancelled', label: 'Cancelled' }
    ], () => {
      if (bulkSelection) bulkSelection.clearSelection();
      loadInvoices();
    });
  });

  document.getElementById('bulkExportBtn')?.addEventListener('click', () => {
    const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
    UI.exportData('invoices', 'csv', { ids: ids.join(',') });
  });

  document.getElementById('createInvoiceBtn')?.addEventListener('click', openCreateInvoiceModal);

  document.getElementById('searchInput')?.addEventListener('input', debounce(() => {
    currentPage = 1;
    loadInvoices();
  }, 350));

  document.getElementById('statusFilter')?.addEventListener('change', () => {
    currentPage = 1;
    loadInvoices();
  });

  document.getElementById('startDateFilter')?.addEventListener('change', () => {
    currentPage = 1;
    loadInvoices();
  });

  document.getElementById('endDateFilter')?.addEventListener('change', () => {
    currentPage = 1;
    loadInvoices();
  });

  document.getElementById('clearFiltersBtn')?.addEventListener('click', () => {
    document.getElementById('searchInput').value = '';
    document.getElementById('statusFilter').value = '';
    document.getElementById('startDateFilter').value = '';
    document.getElementById('endDateFilter').value = '';
    currentPage = 1;
    loadInvoices();
  });

  document.getElementById('prevPageBtn')?.addEventListener('click', () => {
    if (currentPage > 1) {
      currentPage--;
      loadInvoices();
    }
  });

  document.getElementById('nextPageBtn')?.addEventListener('click', () => {
    if (currentPage < currentTotalPages) {
      currentPage++;
      loadInvoices();
    }
  });

  document.getElementById('addItemBtn')?.addEventListener('click', () => {
    addItemRow();
  });

  document.getElementById('invoiceForm')?.addEventListener('submit', handleInvoiceSubmit);
  document.getElementById('quickPaymentForm')?.addEventListener('submit', handleQuickPaymentSubmit);
}

async function loadLookups() {
  try {
    const [prodRes, custRes, dealsRes] = await Promise.all([
      ApiClient.get('/api/products?per_page=100'),
      ApiClient.get('/api/customers?per_page=100'),
      ApiClient.get('/api/deals?per_page=100')
    ]);

    if (prodRes.success && prodRes.data?.data?.products) {
      cachedProducts = prodRes.data.data.products;
    }

    if (custRes.success && custRes.data?.customers) {
      cachedCustomers = custRes.data.customers;
      const custSel = document.getElementById('invCustomer');
      if (custSel) {
        custSel.innerHTML = '<option value="">-- Select Customer --</option>' +
          cachedCustomers.map(c => `<option value="${c.id}">${UI.escapeHtml(c.first_name)} ${UI.escapeHtml(c.last_name)} ${c.company_name ? `(${UI.escapeHtml(c.company_name)})` : ''}</option>`).join('');
      }
    }

    if (dealsRes.success && dealsRes.data?.deals) {
      const dealSel = document.getElementById('invDeal');
      if (dealSel) {
        dealSel.innerHTML = '<option value="">-- None --</option>' +
          dealsRes.data.deals.map(d => `<option value="${d.id}">${UI.escapeHtml(d.title)} (${UI.formatCurrency(d.value)})</option>`).join('');
      }
    }
  } catch (e) {
    console.warn('Failed to load invoice lookups', e);
  }
}

async function loadInvoices() {
  const tbody = document.getElementById('invoicesTableBody');
  if (!tbody) return;

  if (bulkSelection) bulkSelection.clearSelection();

  const search = document.getElementById('searchInput')?.value.trim() || '';
  const status = document.getElementById('statusFilter')?.value || '';
  const startDate = document.getElementById('startDateFilter')?.value || '';
  const endDate = document.getElementById('endDateFilter')?.value || '';

  const params = new URLSearchParams({
    page: currentPage,
    per_page: 15
  });
  if (search) params.append('search', search);
  if (status) params.append('status', status);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  try {
    const res = await ApiClient.get(`/api/invoices?${params.toString()}`);
    if (!res.success) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: #e53e3e; padding: 24px;">Failed to load invoices: ${UI.escapeHtml(res.data?.message || 'Server error')}</td></tr>`;
      return;
    }

    const { invoices, summary, total, page, total_pages } = res.data.data;
    currentPage = page;
    currentTotalPages = total_pages || 1;

    // Update Summary Cards
    document.getElementById('statTotalInvoiced').textContent = UI.formatCurrency(summary.total_invoiced);
    document.getElementById('statTotalPaid').textContent = UI.formatCurrency(summary.total_paid);
    document.getElementById('statOutstanding').textContent = UI.formatCurrency(summary.total_outstanding);
    document.getElementById('statInvoiceCount').textContent = summary.total_count;

    // Update Pagination
    document.getElementById('paginationInfo').textContent = `Showing ${invoices.length} of ${total} invoices (Page ${page} of ${currentTotalPages})`;
    document.getElementById('prevPageBtn').disabled = currentPage <= 1;
    document.getElementById('nextPageBtn').disabled = currentPage >= currentTotalPages;

    if (invoices.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="10" style="text-align: center; padding: 48px 16px;">
            <div style="font-size: 2.5rem; margin-bottom: 8px;">🧾</div>
            <div style="font-weight: 600; font-size: 1.1rem; color: #2d3748;">No Invoices Found</div>
            <p style="color: #718096; margin-top: 4px;">Click "+ Create Invoice" to generate your first bill.</p>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = invoices.map(inv => {
      let badge = '';
      if (inv.status === 'paid') {
        badge = '<span class="status-badge" style="background: #e6fffa; color: #234e52; border: 1px solid #b2f5ea;">Paid</span>';
      } else if (inv.status === 'partially_paid') {
        badge = '<span class="status-badge" style="background: #ebf8ff; color: #2b6cb0; border: 1px solid #bee3f8;">Partially Paid</span>';
      } else if (inv.status === 'overdue') {
        badge = '<span class="status-badge" style="background: #fff5f5; color: #c53030; border: 1px solid #fed7d7;">Overdue</span>';
      } else if (inv.status === 'sent') {
        badge = '<span class="status-badge" style="background: #fffaf0; color: #c05621; border: 1px solid #feebc8;">Sent</span>';
      } else if (inv.status === 'cancelled') {
        badge = '<span class="status-badge" style="background: #edf2f7; color: #718096;">Cancelled</span>';
      } else {
        badge = '<span class="status-badge" style="background: #edf2f7; color: #4a5568;">Draft</span>';
      }

      return `
        <tr>
          <td style="text-align: center;"><input type="checkbox" class="invoice-row-cb" value="${inv.id}"></td>
          <td style="font-family: monospace; font-weight: 700; color: #2b6cb0;">${UI.escapeHtml(inv.invoice_number)}</td>
          <td>
            <div style="font-weight: 600; color: #2d3748;">${UI.escapeHtml(inv.customer_name)}</div>
            ${inv.company_name ? `<div style="font-size: 0.8rem; color: #718096;">${UI.escapeHtml(inv.company_name)}</div>` : ''}
          </td>
          <td>${UI.formatDate(inv.invoice_date)}</td>
          <td>${UI.formatDate(inv.due_date)}</td>
          <td style="font-weight: 700; color: #1a202c;">${UI.formatCurrency(inv.total_amount)}</td>
          <td style="color: #2f855a; font-weight: 600;">${UI.formatCurrency(inv.paid_amount)}</td>
          <td style="color: ${inv.remaining_amount > 0 ? '#dd6b20' : '#718096'}; font-weight: 600;">${UI.formatCurrency(inv.remaining_amount)}</td>
          <td>${badge}</td>
          <td style="text-align: right; white-space: nowrap;">
            <button class="btn btn-secondary btn-sm" onclick="viewInvoice(${inv.id})">View</button>
            <button class="btn btn-secondary btn-sm" style="margin-left: 4px;" onclick="downloadInvoicePdf(${inv.id})" title="Download PDF">📄 PDF</button>
            ${inv.remaining_amount > 0 && inv.status !== 'cancelled' ? `
              <button class="btn btn-primary btn-sm" style="margin-left: 4px; background: #2f855a;" onclick="openQuickPaymentModal(${inv.id}, '${inv.invoice_number}', ${inv.remaining_amount})">Pay</button>
            ` : ''}
            <button class="btn btn-secondary btn-sm" style="margin-left: 4px;" onclick="openEditInvoiceModal(${inv.id})">Edit</button>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load invoices', err);
    tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: #e53e3e; padding: 24px;">An unexpected error occurred.</td></tr>`;
  }
}

function openCreateInvoiceModal() {
  document.getElementById('invoiceForm').reset();
  document.getElementById('invoiceId').value = '';
  document.getElementById('invoiceModalTitle').textContent = 'Create New Invoice';
  document.getElementById('invStatus').value = 'sent';

  const today = new Date().toISOString().split('T')[0];
  const dueDate = new Date(Date.now() + 15 * 86400000).toISOString().split('T')[0];
  document.getElementById('invDate').value = today;
  document.getElementById('invDueDate').value = dueDate;

  const container = document.getElementById('itemsContainer');
  container.innerHTML = '';
  addItemRow(); // Start with 1 item row
  recalculateTotals();

  UI.openModal('invoiceModal');
}

function addItemRow(itemData = {}) {
  const container = document.getElementById('itemsContainer');
  const rowId = 'item_' + Date.now() + '_' + Math.random().toString(36).substr(2, 4);

  const row = document.createElement('div');
  row.id = rowId;
  row.className = 'invoice-item-row';

  let productOptions = '<option value="">-- Custom / Product --</option>';
  cachedProducts.forEach(p => {
    const isSelected = itemData.product_id && String(itemData.product_id) === String(p.id);
    productOptions += `<option value="${p.id}" data-price="${p.price}" data-tax="${p.tax_percentage}" data-discount="${p.discount_percentage}" ${isSelected ? 'selected' : ''}>${UI.escapeHtml(p.name)} (${UI.formatCurrency(p.price)})</option>`;
  });

  row.innerHTML = `
    <div>
      <select class="form-control item-product-select" style="font-size: 0.85rem;">
        ${productOptions}
      </select>
    </div>
    <div>
      <input type="text" class="form-control item-desc" placeholder="Item description" value="${UI.escapeHtml(itemData.description || '')}" style="font-size: 0.85rem;">
    </div>
    <div>
      <input type="number" class="form-control item-qty" min="1" value="${itemData.quantity || 1}" style="font-size: 0.85rem;">
    </div>
    <div>
      <input type="number" class="form-control item-price" step="0.01" min="0" placeholder="0.00" value="${itemData.unit_price || 0.00}" style="font-size: 0.85rem;">
    </div>
    <div>
      <input type="number" class="form-control item-tax" step="0.01" min="0" max="100" value="${itemData.tax_percentage || 0}" style="font-size: 0.85rem;">
    </div>
    <div>
      <input type="number" class="form-control item-disc" step="0.01" min="0" max="100" value="${itemData.discount_percentage || 0}" style="font-size: 0.85rem;">
    </div>
    <div class="item-total" style="font-weight: 700; color: #2d3748; font-size: 0.9rem; text-align: right;">
      ₹0.00
    </div>
    <div>
      <button type="button" class="btn btn-danger btn-sm" style="padding: 4px 8px;" onclick="removeItemRow('${rowId}')">✕</button>
    </div>
  `;

  container.appendChild(row);

  // Wire product change autofill
  const sel = row.querySelector('.item-product-select');
  sel.addEventListener('change', () => {
    const opt = sel.options[sel.selectedIndex];
    if (opt && opt.value) {
      row.querySelector('.item-price').value = opt.getAttribute('data-price') || 0;
      row.querySelector('.item-tax').value = opt.getAttribute('data-tax') || 0;
      row.querySelector('.item-disc').value = opt.getAttribute('data-discount') || 0;
      if (!row.querySelector('.item-desc').value) {
        row.querySelector('.item-desc').value = opt.text.split(' (')[0];
      }
    }
    recalculateTotals();
  });

  // Wire input listeners for dynamic calculation
  row.querySelectorAll('input').forEach(inp => {
    inp.addEventListener('input', recalculateTotals);
  });

  recalculateTotals();
}

function removeItemRow(rowId) {
  const container = document.getElementById('itemsContainer');
  const row = document.getElementById(rowId);
  if (row) row.remove();
  if (container.children.length === 0) {
    addItemRow();
  }
  recalculateTotals();
}

function recalculateTotals() {
  const rows = document.querySelectorAll('.invoice-item-row');
  let subtotal = 0;
  let totalTax = 0;
  let totalDiscount = 0;

  rows.forEach(row => {
    const qty = parseFloat(row.querySelector('.item-qty')?.value) || 0;
    const price = parseFloat(row.querySelector('.item-price')?.value) || 0;
    const taxPct = parseFloat(row.querySelector('.item-tax')?.value) || 0;
    const discPct = parseFloat(row.querySelector('.item-disc')?.value) || 0;

    const base = qty * price;
    const tax = base * (taxPct / 100);
    const disc = base * (discPct / 100);
    const lineTotal = base + tax - disc;

    subtotal += base;
    totalTax += tax;
    totalDiscount += disc;

    const totalEl = row.querySelector('.item-total');
    if (totalEl) totalEl.textContent = UI.formatCurrency(lineTotal);
  });

  const finalTotal = subtotal + totalTax - totalDiscount;

  document.getElementById('previewSubtotal').textContent = UI.formatCurrency(subtotal);
  document.getElementById('previewTax').textContent = UI.formatCurrency(totalTax);
  document.getElementById('previewDiscount').textContent = '- ' + UI.formatCurrency(totalDiscount);
  document.getElementById('previewTotal').textContent = UI.formatCurrency(finalTotal);
}

async function handleInvoiceSubmit(e) {
  e.preventDefault();
  const id = document.getElementById('invoiceId').value;
  const isEdit = Boolean(id);

  const rows = document.querySelectorAll('.invoice-item-row');
  const items = [];
  rows.forEach(row => {
    const prodId = row.querySelector('.item-product-select')?.value;
    const desc = row.querySelector('.item-desc')?.value.trim();
    const qty = parseInt(row.querySelector('.item-qty')?.value) || 1;
    const price = parseFloat(row.querySelector('.item-price')?.value) || 0;
    const taxPct = parseFloat(row.querySelector('.item-tax')?.value) || 0;
    const discPct = parseFloat(row.querySelector('.item-disc')?.value) || 0;

    items.push({
      product_id: prodId ? parseInt(prodId) : null,
      description: desc,
      quantity: qty,
      unit_price: price,
      tax_percentage: taxPct,
      discount_percentage: discPct
    });
  });

  if (items.length === 0) {
    UI.showToast('Please add at least one line item to the invoice', 'warning');
    return;
  }

  const payload = {
    customer_id: parseInt(document.getElementById('invCustomer').value),
    deal_id: document.getElementById('invDeal').value ? parseInt(document.getElementById('invDeal').value) : null,
    invoice_number: document.getElementById('invNumber').value.trim() || undefined,
    invoice_date: document.getElementById('invDate').value,
    due_date: document.getElementById('invDueDate').value,
    status: document.getElementById('invStatus').value,
    notes: document.getElementById('invNotes').value.trim() || undefined,
    items: items
  };

  const btn = document.getElementById('saveInvoiceBtn');
  btn.disabled = true;
  btn.textContent = 'Saving...';

  try {
    let res;
    if (isEdit) {
      res = await ApiClient.put(`/api/invoices/${id}`, payload);
    } else {
      res = await ApiClient.post('/api/invoices', payload);
    }

    if (res.success) {
      UI.showToast(isEdit ? 'Invoice updated successfully' : 'Invoice created successfully', 'success');
      UI.closeModal('invoiceModal');
      loadInvoices();
    } else {
      UI.showToast(res.data?.message || 'Failed to save invoice', 'danger');
    }
  } catch (err) {
    UI.showToast('Error saving invoice', 'danger');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save Invoice';
  }
}

async function openEditInvoiceModal(invoiceId) {
  try {
    const res = await ApiClient.get(`/api/invoices/${invoiceId}`);
    if (!res.success) {
      UI.showToast('Failed to load invoice details', 'danger');
      return;
    }
    const inv = res.data.invoice;

    document.getElementById('invoiceId').value = inv.id;
    document.getElementById('invoiceModalTitle').textContent = `Edit Invoice ${inv.invoice_number}`;
    document.getElementById('invCustomer').value = inv.customer_id;
    if (document.getElementById('invDeal')) document.getElementById('invDeal').value = inv.deal_id || '';
    document.getElementById('invNumber').value = inv.invoice_number;
    document.getElementById('invDate').value = inv.invoice_date;
    document.getElementById('invDueDate').value = inv.due_date;
    document.getElementById('invStatus').value = inv.status;
    document.getElementById('invNotes').value = inv.notes || '';

    const container = document.getElementById('itemsContainer');
    container.innerHTML = '';
    if (Array.isArray(inv.items) && inv.items.length > 0) {
      inv.items.forEach(itm => addItemRow(itm));
    } else {
      addItemRow();
    }
    recalculateTotals();

    UI.openModal('invoiceModal');
  } catch (err) {
    UI.showToast('Error opening edit modal', 'danger');
  }
}

async function viewInvoice(invoiceId) {
  currentViewInvoiceId = invoiceId;
  try {
    const res = await ApiClient.get(`/api/invoices/${invoiceId}`);
    if (!res.success) {
      UI.showToast('Invoice not found', 'danger');
      return;
    }
    const inv = res.data.invoice;

    const printable = document.getElementById('printableInvoice');
    printable.innerHTML = `
      <div style="padding: 24px; font-family: sans-serif; color: #2d3748;">
        <!-- Header -->
        <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #073472; padding-bottom: 16px; margin-bottom: 20px;">
          <div>
            <img src="assets/images/apex-crm-logo.png" alt="Apex CRM" style="height: 48px; margin-bottom: 6px;">
            <div style="font-size: 0.85rem; color: #718096;">APEX CRM Solutions & Services</div>
          </div>
          <div style="text-align: right;">
            <h2 style="margin: 0; color: #073472; font-size: 1.6rem;">TAX INVOICE</h2>
            <div style="font-weight: 700; font-size: 1.1rem; color: #FD6713; margin-top: 4px;">${UI.escapeHtml(inv.invoice_number)}</div>
            <div style="font-size: 0.85rem; color: #718096; margin-top: 2px;">Date: ${UI.formatDate(inv.invoice_date)}</div>
            <div style="font-size: 0.85rem; color: #718096;">Due Date: ${UI.formatDate(inv.due_date)}</div>
          </div>
        </div>

        <!-- Bill To -->
        <div style="display: flex; justify-content: space-between; margin-bottom: 24px;">
          <div style="max-width: 320px;">
            <div style="font-size: 0.8rem; font-weight: 700; color: #a0aec0; text-transform: uppercase;">Billed To:</div>
            <div style="font-size: 1.1rem; font-weight: 700; color: #1a202c; margin-top: 2px;">${UI.escapeHtml(inv.customer_name)}</div>
            ${inv.company_name ? `<div style="font-weight: 600; color: #4a5568;">${UI.escapeHtml(inv.company_name)}</div>` : ''}
            ${inv.customer_email ? `<div style="font-size: 0.85rem; color: #718096;">Email: ${UI.escapeHtml(inv.customer_email)}</div>` : ''}
            ${inv.customer_phone ? `<div style="font-size: 0.85rem; color: #718096;">Phone: ${UI.escapeHtml(inv.customer_phone)}</div>` : ''}
          </div>
          <div style="text-align: right;">
            <div style="font-size: 0.8rem; font-weight: 700; color: #a0aec0; text-transform: uppercase;">Status:</div>
            <div style="margin-top: 4px;">
              <span class="status-badge" style="font-size: 0.9rem; padding: 4px 12px; font-weight: 700;">
                ${inv.status.toUpperCase()}
              </span>
            </div>
          </div>
        </div>

        <!-- Line Items Table -->
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
          <thead>
            <tr style="background: #edf2f7; border-bottom: 2px solid #cbd5e0; text-align: left; font-size: 0.85rem;">
              <th style="padding: 10px;">Item / Description</th>
              <th style="padding: 10px; text-align: center;">Qty</th>
              <th style="padding: 10px; text-align: right;">Unit Price</th>
              <th style="padding: 10px; text-align: right;">Tax %</th>
              <th style="padding: 10px; text-align: right;">Disc %</th>
              <th style="padding: 10px; text-align: right;">Total</th>
            </tr>
          </thead>
          <tbody>
            ${(inv.items || []).map(it => `
              <tr style="border-bottom: 1px solid #edf2f7; font-size: 0.9rem;">
                <td style="padding: 10px;">
                  <div style="font-weight: 600;">${UI.escapeHtml(it.product_name)}</div>
                  ${it.description ? `<div style="font-size: 0.8rem; color: #718096;">${UI.escapeHtml(it.description)}</div>` : ''}
                </td>
                <td style="padding: 10px; text-align: center;">${it.quantity}</td>
                <td style="padding: 10px; text-align: right;">${UI.formatCurrency(it.unit_price)}</td>
                <td style="padding: 10px; text-align: right;">${it.tax_percentage}%</td>
                <td style="padding: 10px; text-align: right;">${it.discount_percentage}%</td>
                <td style="padding: 10px; text-align: right; font-weight: 600;">${UI.formatCurrency(it.total)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>

        <!-- Summary Totals -->
        <div style="display: flex; justify-content: flex-end; margin-bottom: 24px;">
          <div style="width: 300px; font-size: 0.9rem;">
            <div style="display: flex; justify-content: space-between; padding: 4px 0;">
              <span style="color: #718096;">Subtotal:</span>
              <span style="font-weight: 600;">${UI.formatCurrency(inv.subtotal)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 4px 0;">
              <span style="color: #718096;">Tax Amount:</span>
              <span style="font-weight: 600;">${UI.formatCurrency(inv.tax_amount)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 4px 0;">
              <span style="color: #718096;">Discount:</span>
              <span style="font-weight: 600; color: #e53e3e;">- ${UI.formatCurrency(inv.discount_amount)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-top: 2px solid #073472; font-size: 1.15rem; font-weight: 700; color: #073472;">
              <span>Total Amount:</span>
              <span>${UI.formatCurrency(inv.total_amount)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 4px 0; color: #2f855a;">
              <span>Paid Amount:</span>
              <span style="font-weight: 600;">${UI.formatCurrency(inv.paid_amount)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 4px 0; color: #c53030; font-weight: 700;">
              <span>Remaining Balance:</span>
              <span>${UI.formatCurrency(inv.remaining_amount)}</span>
            </div>
          </div>
        </div>

        ${inv.notes ? `
          <div style="background: #f7fafc; padding: 12px; border-radius: 6px; font-size: 0.85rem; color: #4a5568; border-left: 3px solid #073472;">
            <strong>Notes / Terms:</strong>
            <p style="margin: 4px 0 0;">${UI.escapeHtml(inv.notes)}</p>
          </div>
        ` : ''}

        <!-- Payment History Table if any -->
        ${Array.isArray(inv.payments) && inv.payments.length > 0 ? `
          <div style="margin-top: 24px;">
            <h4 style="font-size: 0.95rem; color: #2d3748; margin-bottom: 8px;">Recorded Payments</h4>
            <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
              <thead>
                <tr style="background: #f7fafc; border-bottom: 1px solid #edf2f7; text-align: left;">
                  <th style="padding: 6px 8px;">Date</th>
                  <th style="padding: 6px 8px;">Method</th>
                  <th style="padding: 6px 8px;">Reference</th>
                  <th style="padding: 6px 8px; text-align: right;">Amount</th>
                </tr>
              </thead>
              <tbody>
                ${inv.payments.map(p => `
                  <tr style="border-bottom: 1px solid #f7fafc;">
                    <td style="padding: 6px 8px;">${UI.formatDate(p.payment_date)}</td>
                    <td style="padding: 6px 8px; text-transform: uppercase;">${p.payment_method}</td>
                    <td style="padding: 6px 8px;">${UI.escapeHtml(p.transaction_reference || '—')}</td>
                    <td style="padding: 6px 8px; text-align: right; font-weight: 600; color: #2f855a;">${UI.formatCurrency(p.amount)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        ` : ''}
      </div>
    `;

    UI.openModal('viewInvoiceModal');
  } catch (err) {
    UI.showToast('Error opening invoice view', 'danger');
  }
}

function openQuickPaymentModal(invoiceId, invoiceNumber, remainingAmount) {
  document.getElementById('quickPaymentForm').reset();
  document.getElementById('payInvoiceId').value = invoiceId;
  document.getElementById('payInvoiceNumber').textContent = invoiceNumber;
  document.getElementById('payRemainingBalance').textContent = UI.formatCurrency(remainingAmount);
  document.getElementById('payAmount').value = remainingAmount;
  document.getElementById('payAmount').max = remainingAmount;
  document.getElementById('payDate').value = new Date().toISOString().split('T')[0];

  UI.openModal('quickPaymentModal');
}

async function handleQuickPaymentSubmit(e) {
  e.preventDefault();
  const invoiceId = parseInt(document.getElementById('payInvoiceId').value);
  const amount = parseFloat(document.getElementById('payAmount').value);

  const payload = {
    invoice_id: invoiceId,
    amount: amount,
    payment_method: document.getElementById('payMethod').value,
    payment_date: document.getElementById('payDate').value,
    transaction_reference: document.getElementById('payTxRef').value.trim() || undefined,
    notes: document.getElementById('payNotes').value.trim() || undefined
  };

  const btn = document.getElementById('savePaymentBtn');
  btn.disabled = true;
  btn.textContent = 'Recording...';

  try {
    const res = await ApiClient.post('/api/payments', payload);
    if (res.success) {
      UI.showToast('Payment recorded successfully', 'success');
      UI.closeModal('quickPaymentModal');
      loadInvoices();
    } else {
      UI.showToast(res.data?.message || 'Failed to record payment', 'danger');
    }
  } catch (err) {
    UI.showToast('Error recording payment', 'danger');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Record Payment';
  }
}

function debounce(fn, delay) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}
