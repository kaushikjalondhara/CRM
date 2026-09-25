/**
 * CRM Customers Management Module
 * Supports CRUD, Search, Status Filter, Pagination, Notes, Document Uploads, and 360-View.
 */

let currentPage = 1;
let currentSearch = '';
let currentStatus = '';
let bulkSelection = null;

document.addEventListener('DOMContentLoaded', async () => {
  if (typeof Auth !== 'undefined') {
    const user = await Auth.requireAuth();
    if (!user) return;
  }

  // If on customer-details.html
  const urlParams = new URLSearchParams(window.location.search);
  const customerId = urlParams.get('id');

  if (customerId && document.getElementById('customer360Container')) {
    loadCustomer360Details(customerId);
    initCustomerDetailsEvents(customerId);
  } else if (document.getElementById('customerTableBody')) {
    // On customers.html list page
    initCustomersListEvents();
    loadCustomers();
  }
});

/**
 * ============================================================================
 * CUSTOMERS LISTING & CRUD
 * ============================================================================
 */

function initCustomersListEvents() {
  // Bulk selection setup
  bulkSelection = UI.initBulkSelection({
    selectAllId: 'selectAll',
    rowSelector: '.customer-row-cb',
    toolbarId: 'bulkActionsToolbar',
    countId: 'bulkSelectedCount'
  });

  // Import button
  const importBtn = document.getElementById('importCustomersBtn');
  if (importBtn) {
    importBtn.addEventListener('click', () => {
      UI.openImportModal('customers', () => {
        loadCustomers();
      });
    });
  }

  // Bulk actions
  const bulkDeleteBtn = document.getElementById('bulkDeleteBtn');
  if (bulkDeleteBtn) {
    bulkDeleteBtn.addEventListener('click', () => {
      const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
      UI.bulkDelete('customers', ids, () => {
        if (bulkSelection) bulkSelection.clearSelection();
        loadCustomers();
      });
    });
  }

  const bulkStatusBtn = document.getElementById('bulkStatusBtn');
  if (bulkStatusBtn) {
    bulkStatusBtn.addEventListener('click', () => {
      const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
      UI.bulkStatus('customers', ids, [
        { value: 'active', label: 'Active' },
        { value: 'inactive', label: 'Inactive' },
        { value: 'prospect', label: 'Prospect' },
        { value: 'blocked', label: 'Blocked' }
      ], () => {
        if (bulkSelection) bulkSelection.clearSelection();
        loadCustomers();
      });
    });
  }

  const bulkAssignBtn = document.getElementById('bulkAssignBtn');
  if (bulkAssignBtn) {
    bulkAssignBtn.addEventListener('click', () => {
      const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
      UI.bulkAssign('customers', ids, () => {
        if (bulkSelection) bulkSelection.clearSelection();
        loadCustomers();
      });
    });
  }

  const bulkExportBtn = document.getElementById('bulkExportBtn');
  if (bulkExportBtn) {
    bulkExportBtn.addEventListener('click', () => {
      const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
      UI.exportData('customers', 'csv', { ids: ids.join(',') });
    });
  }

  // Search input
  const searchInput = document.getElementById('customerSearch');
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener('input', (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        currentSearch = e.target.value.trim();
        currentPage = 1;
        loadCustomers();
      }, 350);
    });
  }

  // Status filter
  const statusFilter = document.getElementById('customerStatusFilter');
  if (statusFilter) {
    statusFilter.addEventListener('change', (e) => {
      currentStatus = e.target.value;
      currentPage = 1;
      loadCustomers();
    });
  }

  // Add Customer Button
  const addBtn = document.getElementById('addCustomerBtn');
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      resetCustomerForm();
      document.getElementById('customerModalTitle').textContent = 'Add New Customer';
      UI.loadAssignees('customerAssignedTo');
      UI.openModal('customerModal');
    });
  }

  // Customer Form Submit
  const form = document.getElementById('customerForm');
  if (form) {
    form.addEventListener('submit', handleCustomerFormSubmit);
  }
}

async function loadCustomers() {
  const tbody = document.getElementById('customerTableBody');
  const paginationEl = document.getElementById('customerPagination');
  if (!tbody) return;

  if (bulkSelection) bulkSelection.clearSelection();

  tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 24px; color: var(--text-muted);">Loading customers...</td></tr>';

  const params = new URLSearchParams();
  params.append('page', currentPage);
  params.append('per_page', 10);
  if (currentSearch) params.append('search', currentSearch);
  if (currentStatus) params.append('status', currentStatus);

  try {
    const res = await ApiClient.get(`/api/customers?${params.toString()}`);
    if (!res.success || !res.data) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 24px; color: var(--danger);">${UI.escapeHtml(res.error || 'Failed to load customers')}</td></tr>`;
      return;
    }

    const { customers, pagination } = res.data;
    if (!customers || customers.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8">
            <div class="empty-state">
              <div class="empty-state-icon">👥</div>
              <div class="empty-state-text">No customers found</div>
              <div class="empty-state-subtext">Click "New Customer" to create your first record.</div>
            </div>
          </td>
        </tr>
      `;
      if (paginationEl) paginationEl.innerHTML = '';
      return;
    }

    tbody.innerHTML = customers.map(c => {
      const name = `${c.first_name || ''} ${c.last_name || ''}`.trim() || '—';
      const company = c.company_name ? `<div style="font-size: 0.75rem; color: var(--text-muted);">${UI.escapeHtml(c.company_name)}</div>` : '';
      const email = c.email ? `<div><a href="mailto:${UI.escapeHtml(c.email)}">${UI.escapeHtml(c.email)}</a></div>` : '—';
      const phone = c.phone ? `<div style="font-size: 0.75rem; color: var(--text-muted);">${UI.escapeHtml(c.phone)}</div>` : '';
      const assigned = c.assigned_first_name ? `${UI.escapeHtml(c.assigned_first_name)} ${UI.escapeHtml(c.assigned_last_name || '')}` : '<span style="color:var(--text-muted);">Unassigned</span>';
      const statusBadge = c.status === 'active' ? 'badge-success' : 'badge-secondary';

      return `
        <tr>
          <td style="text-align: center;"><input type="checkbox" class="customer-row-cb" value="${c.id}"></td>
          <td><span style="font-family: monospace; font-weight: 600; color: var(--primary);">${UI.escapeHtml(c.customer_code || '—')}</span></td>
          <td>
            <strong>${UI.escapeHtml(name)}</strong>
            ${company}
          </td>
          <td>
            ${email}
            ${phone}
          </td>
          <td>${assigned}</td>
          <td><span class="badge ${statusBadge}">${UI.escapeHtml(c.status)}</span></td>
          <td>${UI.formatDate(c.created_at)}</td>
          <td>
            <div class="table-actions">
              <a href="customer-details.html?id=${c.id}" class="action-btn" title="View 360 Details">👁 View</a>
              <button class="action-btn" onclick="editCustomer(${c.id})" title="Edit">✏ Edit</button>
              <button class="action-btn btn-danger" onclick="deleteCustomer(${c.id})" title="Delete">🗑</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    renderPagination(paginationEl, pagination, (newPage) => {
      currentPage = newPage;
      loadCustomers();
    });

  } catch (err) {
    console.error('Failed to load customers:', err);
  }
}

function renderPagination(container, p, onPageChange) {
  if (!container || !p || p.pages <= 1) {
    if (container) container.innerHTML = '';
    return;
  }

  const startRecord = (p.page - 1) * p.per_page + 1;
  const endRecord = Math.min(p.page * p.per_page, p.total);

  container.innerHTML = `
    <div>Showing <strong>${startRecord}-${endRecord}</strong> of <strong>${p.total}</strong> customers</div>
    <div class="pagination-controls">
      <button class="page-btn" ${p.page <= 1 ? 'disabled' : ''} id="prevPageBtn">Previous</button>
      <span style="display:inline-flex; align-items:center; padding: 0 8px; font-weight:600;">Page ${p.page} of ${p.pages}</span>
      <button class="page-btn" ${p.page >= p.pages ? 'disabled' : ''} id="nextPageBtn">Next</button>
    </div>
  `;

  document.getElementById('prevPageBtn')?.addEventListener('click', () => onPageChange(p.page - 1));
  document.getElementById('nextPageBtn')?.addEventListener('click', () => onPageChange(p.page + 1));
}

function resetCustomerForm() {
  const form = document.getElementById('customerForm');
  if (form) form.reset();
  document.getElementById('customerId').value = '';
}

async function editCustomer(id) {
  try {
    const res = await ApiClient.get(`/api/customers/${id}`);
    if (!res.success || !res.data || !res.data.customer) {
      UI.showToast(res.error || 'Failed to load customer details', 'danger');
      return;
    }

    const c = res.data.customer;
    document.getElementById('customerId').value = c.id;
    document.getElementById('customerFirstName').value = c.first_name || '';
    document.getElementById('customerLastName').value = c.last_name || '';
    document.getElementById('customerCompany').value = c.company_name || '';
    document.getElementById('customerEmail').value = c.email || '';
    document.getElementById('customerPhone').value = c.phone || '';
    document.getElementById('customerWebsite').value = c.website || '';
    document.getElementById('customerAddress').value = c.address || '';
    document.getElementById('customerCity').value = c.city || '';
    document.getElementById('customerState').value = c.state || '';
    document.getElementById('customerPostalCode').value = c.postal_code || '';
    document.getElementById('customerCountry').value = c.country || '';
    document.getElementById('customerIndustry').value = c.industry || '';
    document.getElementById('customerStatus').value = c.status || 'active';

    await UI.loadAssignees('customerAssignedTo', c.assigned_to);

    document.getElementById('customerModalTitle').textContent = 'Edit Customer';
    UI.openModal('customerModal');
  } catch (err) {
    UI.showToast('Error fetching customer for edit', 'danger');
  }
}

async function handleCustomerFormSubmit(e) {
  e.preventDefault();

  const id = document.getElementById('customerId').value;
  const payload = {
    first_name: document.getElementById('customerFirstName').value.trim(),
    last_name: document.getElementById('customerLastName').value.trim(),
    company_name: document.getElementById('customerCompany').value.trim(),
    email: document.getElementById('customerEmail').value.trim(),
    phone: document.getElementById('customerPhone').value.trim(),
    website: document.getElementById('customerWebsite').value.trim(),
    address: document.getElementById('customerAddress').value.trim(),
    city: document.getElementById('customerCity').value.trim(),
    state: document.getElementById('customerState').value.trim(),
    postal_code: document.getElementById('customerPostalCode').value.trim(),
    country: document.getElementById('customerCountry').value.trim(),
    industry: document.getElementById('customerIndustry').value.trim(),
    status: document.getElementById('customerStatus').value,
    assigned_to: document.getElementById('customerAssignedTo').value || null,
  };

  if (!payload.first_name || !payload.email) {
    UI.showToast('First name and email are required.', 'warning');
    return;
  }

  const submitBtn = document.querySelector('#customerForm button[type="submit"]');
  UI.setButtonLoading(submitBtn, true, 'Saving...');

  try {
    let res;
    if (id) {
      res = await ApiClient.put(`/api/customers/${id}`, payload);
    } else {
      res = await ApiClient.post('/api/customers', payload);
    }

    if (res.success) {
      UI.showToast(id ? 'Customer updated successfully!' : 'Customer created successfully!', 'success');
      UI.closeModal('customerModal');
      loadCustomers();
    } else {
      UI.showToast(res.error || 'Operation failed', 'danger');
    }
  } catch (err) {
    UI.showToast('Network error occurred while saving customer', 'danger');
  } finally {
    UI.setButtonLoading(submitBtn, false);
  }
}

async function deleteCustomer(id) {
  const confirmed = await UI.confirm({
    title: 'Delete Customer',
    message: 'Are you sure you want to delete this customer record? All associated notes and documents may be affected.',
    confirmText: 'Delete Customer',
    isDanger: true
  });
  if (!confirmed) return;

  const res = await ApiClient.delete(`/api/customers/${id}`);
  if (res.success) {
    UI.showToast('Customer deleted successfully', 'success');
    loadCustomers();
  } else {
    UI.showToast(res.error || 'Failed to delete customer', 'danger');
  }
}

/**
 * ============================================================================
 * CUSTOMER 360-VIEW DETAILS
 * ============================================================================
 */

async function loadCustomer360Details(id) {
  const container = document.getElementById('customer360Container');
  if (!container) return;

  try {
    const res = await ApiClient.get(`/api/customers/${id}/360`);
    if (!res.success || !res.data) {
      container.innerHTML = `<div class="empty-state"><div class="empty-state-text" style="color:var(--danger);">${UI.escapeHtml(res.error || 'Failed to load details')}</div></div>`;
      return;
    }

    const { customer, deals, invoices, payments, tasks, calls, meetings, notes, documents, timeline, summary } = res.data;

    // Header info
    document.getElementById('c360Name').textContent = `${customer.first_name || ''} ${customer.last_name || ''}`.trim();
    document.getElementById('c360Company').textContent = customer.company_name || 'No Company';
    document.getElementById('c360Code').textContent = customer.customer_code || '—';
    document.getElementById('c360StatusBadge').className = `badge ${customer.status === 'active' ? 'badge-success' : 'badge-secondary'}`;
    document.getElementById('c360StatusBadge').textContent = customer.status;

    // Financial KPI Summary
    if (summary) {
      if (document.getElementById('c360TotalInvoiced')) document.getElementById('c360TotalInvoiced').textContent = UI.formatCurrency(summary.total_invoiced);
      if (document.getElementById('c360TotalPaid')) document.getElementById('c360TotalPaid').textContent = UI.formatCurrency(summary.total_paid);
      if (document.getElementById('c360Outstanding')) document.getElementById('c360Outstanding').textContent = UI.formatCurrency(summary.outstanding_balance);
      if (document.getElementById('c360DealsValue')) document.getElementById('c360DealsValue').textContent = UI.formatCurrency(summary.total_deals_value);
    }

    // Overview Tab
    document.getElementById('c360Email').textContent = customer.email || '—';
    document.getElementById('c360Phone').textContent = customer.phone || '—';
    document.getElementById('c360Website').textContent = customer.website || '—';
    document.getElementById('c360Industry').textContent = customer.industry || '—';
    document.getElementById('c360Address').textContent = [customer.address, customer.city, customer.state, customer.country].filter(Boolean).join(', ') || '—';
    document.getElementById('c360Assigned').textContent = customer.assigned_first_name ? `${customer.assigned_first_name} ${customer.assigned_last_name || ''}` : 'Unassigned';
    document.getElementById('c360CreatedAt').textContent = UI.formatDate(customer.created_at);

    // Deals Tab
    const dealsList = document.getElementById('c360DealsList');
    if (dealsList) {
      if (!deals || deals.length === 0) {
        dealsList.innerHTML = '<div class="empty-state"><div class="empty-state-text">No deals associated with this customer</div></div>';
      } else {
        dealsList.innerHTML = `
          <table class="data-table">
            <thead>
              <tr>
                <th>Deal Title</th>
                <th>Value</th>
                <th>Stage</th>
                <th>Expected Close</th>
              </tr>
            </thead>
            <tbody>
              ${deals.map(d => `
                <tr>
                  <td><strong>${UI.escapeHtml(d.title)}</strong></td>
                  <td><strong style="color:var(--primary);">${UI.formatCurrency(d.value)}</strong></td>
                  <td><span class="badge badge-primary">${UI.escapeHtml(d.stage)}</span></td>
                  <td>${UI.formatDate(d.expected_close_date)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      }
    }

    // Invoices Tab
    const invList = document.getElementById('c360InvoicesList');
    if (invList) {
      if (!invoices || invoices.length === 0) {
        invList.innerHTML = '<div class="empty-state"><div class="empty-state-text">No invoices generated for this customer</div></div>';
      } else {
        invList.innerHTML = `
          <table class="data-table">
            <thead>
              <tr>
                <th>Invoice #</th>
                <th>Date</th>
                <th>Due Date</th>
                <th>Total</th>
                <th>Paid</th>
                <th>Balance</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${invoices.map(inv => `
                <tr>
                  <td><strong>${UI.escapeHtml(inv.invoice_number)}</strong></td>
                  <td>${UI.formatDate(inv.invoice_date)}</td>
                  <td>${UI.formatDate(inv.due_date)}</td>
                  <td>${UI.formatCurrency(inv.total_amount)}</td>
                  <td style="color:var(--success);">${UI.formatCurrency(inv.paid_amount)}</td>
                  <td style="color:var(--danger); font-weight:600;">${UI.formatCurrency(inv.remaining_amount)}</td>
                  <td><span class="badge badge-secondary">${UI.escapeHtml(inv.status)}</span></td>
                  <td>
                    <button class="btn btn-outline btn-sm" onclick="UI.exportData('invoices', 'pdf', { invoice_id: ${inv.id} })" style="padding:2px 8px; font-size:0.75rem;">
                      📄 PDF
                    </button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      }
    }

    // Payments Tab
    const payList = document.getElementById('c360PaymentsList');
    if (payList) {
      if (!payments || payments.length === 0) {
        payList.innerHTML = '<div class="empty-state"><div class="empty-state-text">No payment records found</div></div>';
      } else {
        payList.innerHTML = `
          <table class="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Amount</th>
                <th>Method</th>
                <th>Reference</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              ${payments.map(p => `
                <tr>
                  <td>${UI.formatDate(p.payment_date)}</td>
                  <td><strong style="color:var(--success);">${UI.formatCurrency(p.amount)}</strong></td>
                  <td><span class="badge badge-info">${UI.escapeHtml(p.payment_method)}</span></td>
                  <td style="font-family:monospace; font-size:0.8rem;">${UI.escapeHtml(p.transaction_reference || '—')}</td>
                  <td>${UI.escapeHtml(p.notes || '—')}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      }
    }

    // Tasks Tab
    const tasksList = document.getElementById('c360TasksList');
    if (tasksList) {
      if (!tasks || tasks.length === 0) {
        tasksList.innerHTML = '<div class="empty-state"><div class="empty-state-text">No tasks logged for this customer</div></div>';
      } else {
        tasksList.innerHTML = `
          <table class="data-table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Due Date</th>
              </tr>
            </thead>
            <tbody>
              ${tasks.map(t => `
                <tr>
                  <td><strong>${UI.escapeHtml(t.title)}</strong></td>
                  <td><span class="badge ${t.priority === 'urgent' ? 'badge-danger' : t.priority === 'high' ? 'badge-warning' : 'badge-secondary'}">${UI.escapeHtml(t.priority)}</span></td>
                  <td><span class="badge ${t.status === 'completed' ? 'badge-success' : 'badge-info'}">${UI.escapeHtml(t.status)}</span></td>
                  <td>${UI.formatDate(t.due_date)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      }
    }

    // Calls Tab
    const callsList = document.getElementById('c360CallsList');
    if (callsList) {
      if (!calls || calls.length === 0) {
        callsList.innerHTML = '<div class="empty-state"><div class="empty-state-text">No call logs recorded</div></div>';
      } else {
        callsList.innerHTML = `
          <table class="data-table">
            <thead>
              <tr>
                <th>Subject</th>
                <th>Type</th>
                <th>Status</th>
                <th>Scheduled At</th>
              </tr>
            </thead>
            <tbody>
              ${calls.map(cl => `
                <tr>
                  <td><strong>${UI.escapeHtml(cl.subject)}</strong></td>
                  <td>${UI.escapeHtml(cl.call_type || 'outbound')}</td>
                  <td><span class="badge badge-info">${UI.escapeHtml(cl.status)}</span></td>
                  <td>${UI.formatDateTime(cl.call_time)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      }
    }

    // Meetings Tab
    const meetingsList = document.getElementById('c360MeetingsList');
    if (meetingsList) {
      if (!meetings || meetings.length === 0) {
        meetingsList.innerHTML = '<div class="empty-state"><div class="empty-state-text">No meetings scheduled</div></div>';
      } else {
        meetingsList.innerHTML = `
          <table class="data-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Start Time</th>
                <th>End Time</th>
                <th>Location</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${meetings.map(m => `
                <tr>
                  <td><strong>${UI.escapeHtml(m.title)}</strong></td>
                  <td>${UI.formatDateTime(m.start_time)}</td>
                  <td>${UI.formatDateTime(m.end_time)}</td>
                  <td>${UI.escapeHtml(m.location || 'Online')}</td>
                  <td><span class="badge badge-secondary">${UI.escapeHtml(m.status)}</span></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      }
    }

    // Timeline Tab
    const timelineList = document.getElementById('c360TimelineList');
    if (timelineList) {
      if (!timeline || timeline.length === 0) {
        timelineList.innerHTML = '<div class="empty-state"><div class="empty-state-text">No activity history recorded yet</div></div>';
      } else {
        timelineList.innerHTML = `
          <div style="display: flex; flex-direction: column; gap: 14px; padding: 10px 0;">
            ${timeline.map(item => `
              <div style="display: flex; gap: 12px; align-items: flex-start;">
                <div style="width: 8px; height: 8px; border-radius: 50%; background: var(--primary); margin-top: 6px; flex-shrink: 0;"></div>
                <div style="flex: 1;">
                  <div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 2px;">
                    <strong style="color: var(--text-primary);">${UI.escapeHtml(item.action || item.type || 'Event')}</strong>
                    <span style="color: var(--text-muted);">${UI.formatDateTime(item.date || item.created_at)}</span>
                  </div>
                  <div style="font-size: 0.85rem; color: var(--text-secondary);">${UI.escapeHtml(item.details || item.description || '')}</div>
                </div>
              </div>
            `).join('')}
          </div>
        `;
      }
    }

    // Notes Tab
    renderCustomerNotes(notes);

    // Documents Tab
    renderCustomerDocuments(documents);

  } catch (err) {
    console.error('Failed to load 360 view:', err);
  }
}

function renderCustomerNotes(notes) {
  const container = document.getElementById('c360NotesTimeline');
  if (!container) return;

  if (!notes || notes.length === 0) {
    container.innerHTML = '<div class="empty-state"><div class="empty-state-text">No notes added yet</div></div>';
    return;
  }

  container.innerHTML = notes.map(n => `
    <div class="timeline-item">
      <div class="timeline-dot"></div>
      <div class="timeline-body">
        <div class="timeline-header">
          <span class="timeline-title">${UI.escapeHtml(n.author_first_name ? `${n.author_first_name} ${n.author_last_name || ''}` : 'Team Member')}</span>
          <span class="timeline-time">${UI.formatDateTime(n.created_at)}</span>
        </div>
        <div class="timeline-desc" style="white-space: pre-wrap;">${UI.escapeHtml(n.note)}</div>
      </div>
    </div>
  `).join('');
}

function renderCustomerDocuments(docs) {
  const container = document.getElementById('c360DocumentsList');
  if (!container) return;

  if (!docs || docs.length === 0) {
    container.innerHTML = '<div class="empty-state"><div class="empty-state-text">No documents uploaded</div></div>';
    return;
  }

  container.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>File Name</th>
          <th>Size</th>
          <th>Uploaded By</th>
          <th>Date</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        ${docs.map(d => `
          <tr>
            <td><strong>📄 ${UI.escapeHtml(d.file_name)}</strong></td>
            <td>${Math.round(d.file_size / 1024)} KB</td>
            <td>${UI.escapeHtml(d.uploader_first_name ? `${d.uploader_first_name} ${d.uploader_last_name || ''}` : 'User')}</td>
            <td>${UI.formatDate(d.created_at)}</td>
            <td>
              <a href="/api/customers/documents/${d.id}/download" target="_blank" class="action-btn">⬇ Download</a>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function initCustomerDetailsEvents(customerId) {
  // Tabs switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const targetId = btn.getAttribute('data-tab');
      document.getElementById(targetId)?.classList.add('active');
    });
  });

  // Add Note Form
  const noteForm = document.getElementById('addNoteForm');
  if (noteForm) {
    noteForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const noteInput = document.getElementById('noteContent');
      const note = noteInput.value.trim();
      if (!note) return;

      const res = await ApiClient.post(`/api/customers/${customerId}/notes`, { note });
      if (res.success) {
        UI.showToast('Note added successfully', 'success');
        noteInput.value = '';
        loadCustomer360Details(customerId);
      } else {
        UI.showToast(res.error || 'Failed to add note', 'danger');
      }
    });
  }

  // Upload Document Form
  const docForm = document.getElementById('uploadDocForm');
  if (docForm) {
    docForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fileInput = document.getElementById('documentFile');
      if (!fileInput.files || !fileInput.files[0]) {
        UI.showToast('Please select a file to upload', 'warning');
        return;
      }

      const formData = new FormData();
      formData.append('file', fileInput.files[0]);

      const res = await ApiClient.upload(`/api/customers/${customerId}/documents`, formData);
      if (res.success) {
        UI.showToast('Document uploaded successfully!', 'success');
        fileInput.value = '';
        loadCustomer360Details(customerId);
      } else {
        UI.showToast(res.error || 'Failed to upload document', 'danger');
      }
    });
  }
}
