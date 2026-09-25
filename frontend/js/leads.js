/**
 * CRM Leads Management Module
 * Handles Lead CRUD, Search, Filter, Pagination, Touchpoint Activities, and Lead-to-Customer Conversion.
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

  const urlParams = new URLSearchParams(window.location.search);
  const leadId = urlParams.get('id');

  if (leadId && document.getElementById('leadDetailsContainer')) {
    loadLeadDetails(leadId);
    initLeadDetailsEvents(leadId);
  } else if (document.getElementById('leadTableBody')) {
    initLeadsListEvents();
    loadLeads();
  }
});

function initLeadsListEvents() {
  // Bulk selection setup
  bulkSelection = UI.initBulkSelection({
    selectAllId: 'selectAll',
    rowSelector: '.lead-row-cb',
    toolbarId: 'bulkActionsToolbar',
    countId: 'bulkSelectedCount'
  });

  // Import button
  const importBtn = document.getElementById('importLeadsBtn');
  if (importBtn) {
    importBtn.addEventListener('click', () => {
      UI.openImportModal('leads', () => {
        loadLeads();
      });
    });
  }

  // Bulk actions
  const bulkDeleteBtn = document.getElementById('bulkDeleteBtn');
  if (bulkDeleteBtn) {
    bulkDeleteBtn.addEventListener('click', () => {
      const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
      UI.bulkDelete('leads', ids, () => {
        if (bulkSelection) bulkSelection.clearSelection();
        loadLeads();
      });
    });
  }

  const bulkStatusBtn = document.getElementById('bulkStatusBtn');
  if (bulkStatusBtn) {
    bulkStatusBtn.addEventListener('click', () => {
      const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
      UI.bulkStatus('leads', ids, [
        { value: 'new', label: 'New' },
        { value: 'contacted', label: 'Contacted' },
        { value: 'qualified', label: 'Qualified' },
        { value: 'proposal', label: 'Proposal' },
        { value: 'negotiation', label: 'Negotiation' },
        { value: 'lost', label: 'Lost' }
      ], () => {
        if (bulkSelection) bulkSelection.clearSelection();
        loadLeads();
      });
    });
  }

  const bulkAssignBtn = document.getElementById('bulkAssignBtn');
  if (bulkAssignBtn) {
    bulkAssignBtn.addEventListener('click', () => {
      const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
      UI.bulkAssign('leads', ids, () => {
        if (bulkSelection) bulkSelection.clearSelection();
        loadLeads();
      });
    });
  }

  const bulkExportBtn = document.getElementById('bulkExportBtn');
  if (bulkExportBtn) {
    bulkExportBtn.addEventListener('click', () => {
      const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
      UI.exportData('leads', 'csv', { ids: ids.join(',') });
    });
  }

  const searchInput = document.getElementById('leadSearch');
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener('input', (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        currentSearch = e.target.value.trim();
        currentPage = 1;
        loadLeads();
      }, 350);
    });
  }

  const statusFilter = document.getElementById('leadStatusFilter');
  if (statusFilter) {
    statusFilter.addEventListener('change', (e) => {
      currentStatus = e.target.value;
      currentPage = 1;
      loadLeads();
    });
  }

  const addBtn = document.getElementById('addLeadBtn');
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      resetLeadForm();
      document.getElementById('leadModalTitle').textContent = 'Add New Lead';
      UI.loadAssignees('leadAssignedTo');
      UI.openModal('leadModal');
    });
  }

  const form = document.getElementById('leadForm');
  if (form) {
    form.addEventListener('submit', handleLeadFormSubmit);
  }
}

async function loadLeads() {
  const tbody = document.getElementById('leadTableBody');
  const paginationEl = document.getElementById('leadPagination');
  if (!tbody) return;

  if (bulkSelection) bulkSelection.clearSelection();

  tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 24px; color: var(--text-muted);">Loading leads...</td></tr>';

  const params = new URLSearchParams();
  params.append('page', currentPage);
  params.append('per_page', 10);
  if (currentSearch) params.append('search', currentSearch);
  if (currentStatus) params.append('status', currentStatus);

  try {
    const res = await ApiClient.get(`/api/leads?${params.toString()}`);
    if (!res.success || !res.data) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 24px; color: var(--danger);">${UI.escapeHtml(res.error || 'Failed to load leads')}</td></tr>`;
      return;
    }

    const { leads, pagination } = res.data;
    if (!leads || leads.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8">
            <div class="empty-state">
              <div class="empty-state-icon">🎯</div>
              <div class="empty-state-text">No leads found</div>
              <div class="empty-state-subtext">Click "New Lead" to capture an opportunity.</div>
            </div>
          </td>
        </tr>
      `;
      if (paginationEl) paginationEl.innerHTML = '';
      return;
    }

    tbody.innerHTML = leads.map(l => {
      const name = `${l.first_name || ''} ${l.last_name || ''}`.trim() || '—';
      const company = l.company_name ? `<div style="font-size: 0.75rem; color: var(--text-muted);">${UI.escapeHtml(l.company_name)}</div>` : '';
      const email = l.email ? `<div><a href="mailto:${UI.escapeHtml(l.email)}">${UI.escapeHtml(l.email)}</a></div>` : '—';
      const phone = l.phone ? `<div style="font-size: 0.75rem; color: var(--text-muted);">${UI.escapeHtml(l.phone)}</div>` : '';
      const assigned = l.assigned_first_name ? `${UI.escapeHtml(l.assigned_first_name)} ${UI.escapeHtml(l.assigned_last_name || '')}` : '<span style="color:var(--text-muted);">Unassigned</span>';

      let statusBadge = 'badge-secondary';
      if (l.status === 'qualified') statusBadge = 'badge-success';
      else if (l.status === 'proposal' || l.status === 'negotiation') statusBadge = 'badge-primary';
      else if (l.status === 'converted') statusBadge = 'badge-success';
      else if (l.status === 'lost') statusBadge = 'badge-danger';
      else if (l.status === 'contacted') statusBadge = 'badge-info';

      const estValue = l.estimated_value ? UI.formatCurrency(l.estimated_value) : '—';

      return `
        <tr>
          <td style="text-align: center;"><input type="checkbox" class="lead-row-cb" value="${l.id}"></td>
          <td>
            <strong>${UI.escapeHtml(name)}</strong>
            ${company}
          </td>
          <td>
            ${email}
            ${phone}
          </td>
          <td><span class="badge ${statusBadge}">${UI.escapeHtml(l.status)}</span></td>
          <td><strong style="color:var(--primary);">${estValue}</strong></td>
          <td>${assigned}</td>
          <td>${UI.formatDate(l.created_at)}</td>
          <td>
            <div class="table-actions">
              <a href="lead-details.html?id=${l.id}" class="action-btn" title="View Touchpoints & Convert">👁 View</a>
              ${l.status !== 'converted' ? `<button class="action-btn" style="color:var(--success); border-color:var(--success);" onclick="convertLeadPrompt(${l.id})" title="Convert to Customer">🔄 Convert</button>` : ''}
              <button class="action-btn" onclick="editLead(${l.id})" title="Edit">✏</button>
              <button class="action-btn btn-danger" onclick="deleteLead(${l.id})" title="Delete">🗑</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    renderLeadPagination(paginationEl, pagination, (newPage) => {
      currentPage = newPage;
      loadLeads();
    });

  } catch (err) {
    console.error('Failed to load leads:', err);
  }
}

function renderLeadPagination(container, p, onPageChange) {
  if (!container || !p || p.pages <= 1) {
    if (container) container.innerHTML = '';
    return;
  }

  const startRecord = (p.page - 1) * p.per_page + 1;
  const endRecord = Math.min(p.page * p.per_page, p.total);

  container.innerHTML = `
    <div>Showing <strong>${startRecord}-${endRecord}</strong> of <strong>${p.total}</strong> leads</div>
    <div class="pagination-controls">
      <button class="page-btn" ${p.page <= 1 ? 'disabled' : ''} id="prevLeadPageBtn">Previous</button>
      <span style="display:inline-flex; align-items:center; padding: 0 8px; font-weight:600;">Page ${p.page} of ${p.pages}</span>
      <button class="page-btn" ${p.page >= p.pages ? 'disabled' : ''} id="nextLeadPageBtn">Next</button>
    </div>
  `;

  document.getElementById('prevLeadPageBtn')?.addEventListener('click', () => onPageChange(p.page - 1));
  document.getElementById('nextLeadPageBtn')?.addEventListener('click', () => onPageChange(p.page + 1));
}

function resetLeadForm() {
  const form = document.getElementById('leadForm');
  if (form) form.reset();
  document.getElementById('leadId').value = '';
}

async function editLead(id) {
  try {
    const res = await ApiClient.get(`/api/leads/${id}`);
    if (!res.success || !res.data || !res.data.lead) {
      UI.showToast(res.error || 'Failed to load lead details', 'danger');
      return;
    }

    const l = res.data.lead;
    document.getElementById('leadId').value = l.id;
    document.getElementById('leadFirstName').value = l.first_name || '';
    document.getElementById('leadLastName').value = l.last_name || '';
    document.getElementById('leadCompany').value = l.company_name || '';
    document.getElementById('leadEmail').value = l.email || '';
    document.getElementById('leadPhone').value = l.phone || '';
    document.getElementById('leadSource').value = l.source || 'website';
    document.getElementById('leadStatus').value = l.status || 'new';
    document.getElementById('leadPriority').value = l.priority || 'medium';
    document.getElementById('leadEstValue').value = l.estimated_value || '';

    await UI.loadAssignees('leadAssignedTo', l.assigned_to);

    document.getElementById('leadModalTitle').textContent = 'Edit Lead';
    UI.openModal('leadModal');
  } catch (err) {
    UI.showToast('Error fetching lead for edit', 'danger');
  }
}

async function handleLeadFormSubmit(e) {
  e.preventDefault();

  const id = document.getElementById('leadId').value;
  const payload = {
    first_name: document.getElementById('leadFirstName').value.trim(),
    last_name: document.getElementById('leadLastName').value.trim(),
    company_name: document.getElementById('leadCompany').value.trim(),
    email: document.getElementById('leadEmail').value.trim(),
    phone: document.getElementById('leadPhone').value.trim(),
    source: document.getElementById('leadSource').value,
    status: document.getElementById('leadStatus').value,
    priority: document.getElementById('leadPriority').value,
    estimated_value: parseFloat(document.getElementById('leadEstValue').value) || 0,
    assigned_to: document.getElementById('leadAssignedTo').value || null,
  };

  if (!payload.first_name || !payload.email) {
    UI.showToast('First name and email are required.', 'warning');
    return;
  }

  const submitBtn = document.querySelector('#leadForm button[type="submit"]');
  UI.setButtonLoading(submitBtn, true, 'Saving...');

  try {
    let res;
    if (id) {
      res = await ApiClient.put(`/api/leads/${id}`, payload);
    } else {
      res = await ApiClient.post('/api/leads', payload);
    }

    if (res.success) {
      UI.showToast(id ? 'Lead updated successfully!' : 'Lead created successfully!', 'success');
      UI.closeModal('leadModal');
      loadLeads();
    } else {
      UI.showToast(res.error || 'Operation failed', 'danger');
    }
  } catch (err) {
    UI.showToast('Network error while saving lead', 'danger');
  } finally {
    UI.setButtonLoading(submitBtn, false);
  }
}

async function deleteLead(id) {
  const confirmed = await UI.confirm({
    title: 'Delete Lead',
    message: 'Are you sure you want to delete this lead record?',
    confirmText: 'Delete Lead',
    isDanger: true
  });
  if (!confirmed) return;

  const res = await ApiClient.delete(`/api/leads/${id}`);
  if (res.success) {
    UI.showToast('Lead deleted successfully', 'success');
    loadLeads();
  } else {
    UI.showToast(res.error || 'Failed to delete lead', 'danger');
  }
}

async function convertLeadPrompt(id) {
  const confirmed = await UI.confirm({
    title: 'Convert Lead to Customer',
    message: 'Convert this lead into an official customer account? This will create a permanent customer profile.',
    confirmText: 'Convert to Customer',
    isDanger: false
  });
  if (!confirmed) return;

  try {
    const res = await ApiClient.post(`/api/leads/${id}/convert`, {});
    if (res.success && res.data) {
      UI.showToast('Lead converted to Customer successfully!', 'success');
      setTimeout(() => {
        window.location.href = `customer-details.html?id=${res.data.customer_id}`;
      }, 1000);
    } else {
      UI.showToast(res.error || 'Lead conversion failed', 'danger');
    }
  } catch (err) {
    UI.showToast('Error converting lead', 'danger');
  }
}

/**
 * ============================================================================
 * LEAD DETAILS & TOUCHPOINT ACTIVITIES
 * ============================================================================
 */

async function loadLeadDetails(id) {
  const container = document.getElementById('leadDetailsContainer');
  if (!container) return;

  try {
    const res = await ApiClient.get(`/api/leads/${id}`);
    if (!res.success || !res.data || !res.data.lead) {
      container.innerHTML = `<div class="empty-state"><div class="empty-state-text" style="color:var(--danger);">${UI.escapeHtml(res.error || 'Failed to load lead')}</div></div>`;
      return;
    }

    const l = res.data.lead;

    document.getElementById('leadDetailName').textContent = `${l.first_name || ''} ${l.last_name || ''}`.trim();
    document.getElementById('leadDetailCompany').textContent = l.company_name || 'No Company';
    document.getElementById('leadDetailStatus').textContent = l.status;
    document.getElementById('leadDetailStatus').className = `badge ${l.status === 'qualified' ? 'badge-success' : 'badge-info'}`;

    document.getElementById('leadDetailEmail').textContent = l.email || '—';
    document.getElementById('leadDetailPhone').textContent = l.phone || '—';
    document.getElementById('leadDetailSource').textContent = l.source || '—';
    document.getElementById('leadDetailPriority').textContent = l.priority || 'medium';
    document.getElementById('leadDetailEstValue').textContent = l.estimated_value ? UI.formatCurrency(l.estimated_value) : '—';
    document.getElementById('leadDetailAssigned').textContent = l.assigned_first_name ? `${l.assigned_first_name} ${l.assigned_last_name || ''}` : 'Unassigned';
    document.getElementById('leadDetailCreatedAt').textContent = UI.formatDate(l.created_at);

    // Convert button in header
    const convertBtn = document.getElementById('leadConvertBtn');
    if (convertBtn) {
      if (l.status === 'converted') {
        convertBtn.textContent = 'Already Converted';
        convertBtn.disabled = true;
        if (l.converted_customer_id) {
          convertBtn.onclick = () => window.location.href = `customer-details.html?id=${l.converted_customer_id}`;
          convertBtn.disabled = false;
          convertBtn.textContent = 'View Customer Profile →';
        }
      } else {
        convertBtn.onclick = () => convertLeadPrompt(l.id);
      }
    }

    // Load touchpoint activities
    loadLeadActivities(id);

  } catch (err) {
    console.error('Failed to load lead details:', err);
  }
}

async function loadLeadActivities(id) {
  const container = document.getElementById('leadActivitiesTimeline');
  if (!container) return;

  try {
    const res = await ApiClient.get(`/api/leads/${id}/activities`);
    if (!res.success || !res.data || !res.data.activities || res.data.activities.length === 0) {
      container.innerHTML = '<div class="empty-state"><div class="empty-state-text">No touchpoint activities recorded yet</div><div class="empty-state-subtext">Add a call, email, or meeting note below.</div></div>';
      return;
    }

    container.innerHTML = res.data.activities.map(act => `
      <div class="timeline-item">
        <div class="timeline-dot"></div>
        <div class="timeline-body">
          <div class="timeline-header">
            <span class="timeline-title">${UI.escapeHtml(act.activity_type.toUpperCase())} by ${UI.escapeHtml(act.user_first_name ? `${act.user_first_name} ${act.user_last_name || ''}` : 'Team Member')}</span>
            <span class="timeline-time">${UI.formatDateTime(act.created_at)}</span>
          </div>
          <div class="timeline-desc" style="white-space: pre-wrap;">${UI.escapeHtml(act.notes || '')}</div>
        </div>
      </div>
    `).join('');

  } catch (err) {
    console.error('Failed to load lead activities:', err);
  }
}

function initLeadDetailsEvents(id) {
  const form = document.getElementById('addLeadActivityForm');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const activity_type = document.getElementById('activityType').value;
      const notes = document.getElementById('activityNotes').value.trim();

      if (!notes) {
        UI.showToast('Please enter interaction notes', 'warning');
        return;
      }

      const res = await ApiClient.post(`/api/leads/${id}/activities`, { activity_type, notes });
      if (res.success) {
        UI.showToast('Activity logged successfully!', 'success');
        document.getElementById('activityNotes').value = '';
        loadLeadActivities(id);
      } else {
        UI.showToast(res.error || 'Failed to log activity', 'danger');
      }
    });
  }
}
