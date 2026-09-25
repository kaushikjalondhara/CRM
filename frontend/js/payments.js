/**
 * CRM Payments Module
 * Handles payment history, recording payments against invoices, and receipt views.
 */

let currentPage = 1;
let currentTotalPages = 1;
let unpaidInvoices = [];

document.addEventListener('DOMContentLoaded', async () => {
  const user = await Auth.requireAuth();
  if (!user) return;

  UI.updateNotificationBadge();
  setupEventListeners();
  loadPayments();
});

function setupEventListeners() {
  document.getElementById('recordPaymentBtn')?.addEventListener('click', openRecordPaymentModal);

  document.getElementById('searchInput')?.addEventListener('input', debounce(() => {
    currentPage = 1;
    loadPayments();
  }, 350));

  document.getElementById('methodFilter')?.addEventListener('change', () => {
    currentPage = 1;
    loadPayments();
  });

  document.getElementById('startDateFilter')?.addEventListener('change', () => {
    currentPage = 1;
    loadPayments();
  });

  document.getElementById('endDateFilter')?.addEventListener('change', () => {
    currentPage = 1;
    loadPayments();
  });

  document.getElementById('clearFiltersBtn')?.addEventListener('click', () => {
    document.getElementById('searchInput').value = '';
    document.getElementById('methodFilter').value = '';
    document.getElementById('startDateFilter').value = '';
    document.getElementById('endDateFilter').value = '';
    currentPage = 1;
    loadPayments();
  });

  document.getElementById('prevPageBtn')?.addEventListener('click', () => {
    if (currentPage > 1) {
      currentPage--;
      loadPayments();
    }
  });

  document.getElementById('nextPageBtn')?.addEventListener('click', () => {
    if (currentPage < currentTotalPages) {
      currentPage++;
      loadPayments();
    }
  });

  document.getElementById('paymentForm')?.addEventListener('submit', handlePaymentSubmit);

  document.getElementById('payInvoiceSelect')?.addEventListener('change', (e) => {
    const invId = e.target.value;
    const box = document.getElementById('invoiceInfoBox');
    const amountInp = document.getElementById('modalPayAmount');

    if (!invId) {
      box.style.display = 'none';
      amountInp.value = '';
      return;
    }

    const selectedInv = unpaidInvoices.find(i => String(i.id) === String(invId));
    if (selectedInv) {
      document.getElementById('boxCustomerName').textContent = selectedInv.customer_name;
      document.getElementById('boxTotalAmount').textContent = UI.formatCurrency(selectedInv.total_amount);
      document.getElementById('boxRemainingAmount').textContent = UI.formatCurrency(selectedInv.remaining_amount);
      box.style.display = 'block';

      amountInp.value = selectedInv.remaining_amount;
      amountInp.max = selectedInv.remaining_amount;
    }
  });
}

async function loadPayments() {
  const tbody = document.getElementById('paymentsTableBody');
  if (!tbody) return;

  const search = document.getElementById('searchInput')?.value.trim() || '';
  const method = document.getElementById('methodFilter')?.value || '';
  const startDate = document.getElementById('startDateFilter')?.value || '';
  const endDate = document.getElementById('endDateFilter')?.value || '';

  const params = new URLSearchParams({
    page: currentPage,
    per_page: 15
  });
  if (search) params.append('search', search);
  if (method) params.append('payment_method', method);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  try {
    const res = await ApiClient.get(`/api/payments?${params.toString()}`);
    if (!res.success) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: #e53e3e; padding: 24px;">Failed to load payments: ${UI.escapeHtml(res.data?.message || 'Server error')}</td></tr>`;
      return;
    }

    const { payments, total_collected, total, page, total_pages } = res.data.data;
    currentPage = page;
    currentTotalPages = total_pages || 1;

    // Update Stats
    document.getElementById('statTotalCollected').textContent = UI.formatCurrency(total_collected);
    document.getElementById('statTotalPayments').textContent = total;
    const avg = total > 0 ? (total_collected / total) : 0;
    document.getElementById('statAveragePayment').textContent = UI.formatCurrency(avg);

    // Update Pagination
    document.getElementById('paginationInfo').textContent = `Showing ${payments.length} of ${total} records (Page ${page} of ${currentTotalPages})`;
    document.getElementById('prevPageBtn').disabled = currentPage <= 1;
    document.getElementById('nextPageBtn').disabled = currentPage >= currentTotalPages;

    if (payments.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align: center; padding: 48px 16px;">
            <div style="font-size: 2.5rem; margin-bottom: 8px;">💳</div>
            <div style="font-weight: 600; font-size: 1.1rem; color: #2d3748;">No Payment Transactions</div>
            <p style="color: #718096; margin-top: 4px;">Click "+ Record Payment" to log a customer remittance.</p>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = payments.map(p => {
      let methodBadge = '<span class="status-badge" style="background: #edf2f7; color: #4a5568; text-transform: uppercase;">' + p.payment_method + '</span>';
      if (p.payment_method === 'upi') {
        methodBadge = '<span class="status-badge" style="background: #ebf8ff; color: #2b6cb0;">UPI</span>';
      } else if (p.payment_method === 'bank_transfer') {
        methodBadge = '<span class="status-badge" style="background: #e6fffa; color: #234e52;">Bank Wire</span>';
      }

      return `
        <tr>
          <td>${UI.formatDate(p.payment_date)}</td>
          <td style="font-family: monospace; font-weight: 700; color: #2b6cb0;">${UI.escapeHtml(p.invoice_number)}</td>
          <td>
            <div style="font-weight: 600; color: #2d3748;">${UI.escapeHtml(p.customer_name)}</div>
            ${p.company_name ? `<div style="font-size: 0.8rem; color: #718096;">${UI.escapeHtml(p.company_name)}</div>` : ''}
          </td>
          <td style="font-weight: 700; color: #2f855a; font-size: 1rem;">${UI.formatCurrency(p.amount)}</td>
          <td>${methodBadge}</td>
          <td style="font-family: monospace; font-size: 0.85rem;">${UI.escapeHtml(p.transaction_reference || '—')}</td>
          <td style="color: #718096; font-size: 0.85rem;">${UI.escapeHtml(p.recorded_by || 'System')}</td>
          <td style="text-align: right; white-space: nowrap;">
            <button class="btn btn-danger btn-sm" onclick="voidPayment(${p.id}, '${UI.escapeHtml(p.invoice_number)}', ${p.amount})">Void</button>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load payments', err);
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: #e53e3e; padding: 24px;">An unexpected error occurred.</td></tr>`;
  }
}

async function openRecordPaymentModal() {
  document.getElementById('paymentForm').reset();
  document.getElementById('modalPayDate').value = new Date().toISOString().split('T')[0];
  document.getElementById('invoiceInfoBox').style.display = 'none';

  const select = document.getElementById('payInvoiceSelect');
  select.innerHTML = '<option value="">Loading invoices...</option>';

  try {
    const res = await ApiClient.get('/api/invoices?per_page=100');
    if (res.success && res.data?.data?.invoices) {
      unpaidInvoices = res.data.data.invoices.filter(i => i.remaining_amount > 0 && i.status !== 'cancelled');

      if (unpaidInvoices.length === 0) {
        select.innerHTML = '<option value="">No unpaid invoices found</option>';
      } else {
        select.innerHTML = '<option value="">-- Choose Unpaid Invoice --</option>' +
          unpaidInvoices.map(i => `
            <option value="${i.id}">
              ${UI.escapeHtml(i.invoice_number)} - ${UI.escapeHtml(i.customer_name)} (Due: ${UI.formatCurrency(i.remaining_amount)})
            </option>
          `).join('');
      }
    }
  } catch (e) {
    select.innerHTML = '<option value="">Error loading invoices</option>';
  }

  UI.openModal('paymentModal');
}

async function handlePaymentSubmit(e) {
  e.preventDefault();
  const invoiceId = parseInt(document.getElementById('payInvoiceSelect').value);
  const amount = parseFloat(document.getElementById('modalPayAmount').value);

  const payload = {
    invoice_id: invoiceId,
    amount: amount,
    payment_method: document.getElementById('modalPayMethod').value,
    payment_date: document.getElementById('modalPayDate').value,
    transaction_reference: document.getElementById('modalPayRef').value.trim() || undefined,
    notes: document.getElementById('modalPayNotes').value.trim() || undefined
  };

  const btn = document.getElementById('submitPaymentBtn');
  UI.setButtonLoading(btn, true, 'Saving...');

  try {
    const res = await ApiClient.post('/api/payments', payload);
    if (res.success) {
      UI.showToast('Payment recorded successfully', 'success');
      UI.closeModal('paymentModal');
      loadPayments();
    } else {
      UI.showToast(res.data?.message || 'Failed to record payment', 'danger');
    }
  } catch (err) {
    UI.showToast('Error recording payment', 'danger');
  } finally {
    UI.setButtonLoading(btn, false);
  }
}

async function voidPayment(paymentId, invoiceNumber, amount) {
  const confirmed = await UI.confirm({
    title: 'Void Payment',
    message: `Are you sure you want to void payment #${paymentId} (${UI.formatCurrency(amount)}) for Invoice ${invoiceNumber}? The invoice remaining balance will be restored.`,
    confirmText: 'Void Payment',
    cancelText: 'Cancel',
    isDanger: true
  });
  if (!confirmed) return;

  try {
    const res = await ApiClient.delete(`/api/payments/${paymentId}`);
    if (res.success) {
      UI.showToast(res.data?.message || 'Payment voided successfully', 'success');
      loadPayments();
    } else {
      UI.showToast(res.data?.message || 'Failed to void payment', 'danger');
    }
  } catch (err) {
    UI.showToast('Error voiding payment', 'danger');
  }
}

function debounce(fn, delay) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}
