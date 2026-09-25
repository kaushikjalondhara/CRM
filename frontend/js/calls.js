/**
 * CRM Calls Management Module
 * Handles scheduling, status updates, outcome logging, and call history tracking.
 */

let currentCallStatusFilter = '';

document.addEventListener('DOMContentLoaded', async () => {
  if (typeof Auth !== 'undefined') {
    const user = await Auth.requireAuth();
    if (!user) return;
  }

  loadCalls();
  initCallEvents();
});

function initCallEvents() {
  const statusFilter = document.getElementById('callStatusFilter');
  if (statusFilter) {
    statusFilter.addEventListener('change', (e) => {
      currentCallStatusFilter = e.target.value;
      loadCalls();
    });
  }

  const addBtn = document.getElementById('addCallBtn');
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      resetCallForm();
      document.getElementById('callModalTitle').textContent = 'Schedule New Call';
      UI.loadAssignees('callUserId');
      UI.openModal('callModal');
    });
  }

  const form = document.getElementById('callForm');
  if (form) {
    form.addEventListener('submit', handleCallFormSubmit);
  }
}

async function loadCalls() {
  const tbody = document.getElementById('callTableBody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 24px; color: var(--text-muted);">Loading call logs...</td></tr>';

  const params = new URLSearchParams();
  if (currentCallStatusFilter) params.append('status', currentCallStatusFilter);

  try {
    const res = await ApiClient.get(`/api/calls?${params.toString()}`);
    if (!res.success || !res.data) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 24px; color: var(--danger);">${UI.escapeHtml(res.error || 'Failed to load calls')}</td></tr>`;
      return;
    }

    const calls = res.data.calls || [];
    if (calls.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7">
            <div class="empty-state">
              <div class="empty-state-icon">📞</div>
              <div class="empty-state-text">No calls found</div>
              <div class="empty-state-subtext">Schedule an outbound or inbound call with a customer or lead.</div>
            </div>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = calls.map(c => {
      let statusBadge = 'badge-secondary';
      if (c.status === 'completed') statusBadge = 'badge-success';
      else if (c.status === 'scheduled') statusBadge = 'badge-primary';
      else if (c.status === 'missed') statusBadge = 'badge-danger';
      else if (c.status === 'cancelled') statusBadge = 'badge-warning';

      const caller = c.user_first_name ? `${UI.escapeHtml(c.user_first_name)} ${UI.escapeHtml(c.user_last_name || '')}` : 'User';
      const duration = c.duration_minutes ? `${c.duration_minutes} min` : '—';
      const contactInfo = c.contact_type ? `${c.contact_type.toUpperCase()} #${c.contact_id || '—'}` : 'Direct Contact';

      return `
        <tr>
          <td>
            <strong>${UI.escapeHtml(c.subject)}</strong>
            ${c.notes ? `<div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;">${UI.escapeHtml(c.notes)}</div>` : ''}
          </td>
          <td><span class="badge badge-info">${contactInfo}</span></td>
          <td><span class="badge ${statusBadge}">${UI.escapeHtml(c.status)}</span></td>
          <td>${UI.formatDateTime(c.call_time)}</td>
          <td>${duration}</td>
          <td>${caller}</td>
          <td>
            <div class="table-actions">
              <button class="action-btn" onclick="editCall(${c.id})" title="Edit Call">✏ Edit</button>
              <button class="action-btn btn-danger" onclick="deleteCall(${c.id})" title="Delete Call">🗑</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load calls:', err);
  }
}

function resetCallForm() {
  const form = document.getElementById('callForm');
  if (form) form.reset();
  document.getElementById('callId').value = '';
}

async function editCall(id) {
  try {
    const res = await ApiClient.get(`/api/calls/${id}`);
    if (!res.success || !res.data || !res.data.call) {
      UI.showToast(res.error || 'Failed to load call', 'danger');
      return;
    }

    const c = res.data.call;
    document.getElementById('callId').value = c.id;
    document.getElementById('callSubject').value = c.subject || '';
    document.getElementById('callContactType').value = c.contact_type || 'customer';
    document.getElementById('callContactId').value = c.contact_id || '';
    document.getElementById('callStatus').value = c.status || 'scheduled';
    document.getElementById('callTime').value = c.call_time ? c.call_time.slice(0, 16) : '';
    document.getElementById('callDuration').value = c.duration_minutes || '';
    document.getElementById('callNotes').value = c.notes || '';

    await UI.loadAssignees('callUserId', c.user_id);

    document.getElementById('callModalTitle').textContent = 'Edit Call';
    UI.openModal('callModal');
  } catch (err) {
    UI.showToast('Error fetching call details', 'danger');
  }
}

async function handleCallFormSubmit(e) {
  e.preventDefault();

  const id = document.getElementById('callId').value;
  const payload = {
    subject: document.getElementById('callSubject').value.trim(),
    contact_type: document.getElementById('callContactType').value || null,
    contact_id: parseInt(document.getElementById('callContactId').value) || null,
    status: document.getElementById('callStatus').value,
    call_time: document.getElementById('callTime').value,
    duration_minutes: parseInt(document.getElementById('callDuration').value) || null,
    notes: document.getElementById('callNotes').value.trim(),
    user_id: document.getElementById('callUserId').value || null,
  };

  if (!payload.subject || !payload.call_time) {
    UI.showToast('Subject and Call Time are required.', 'warning');
    return;
  }

  const submitBtn = document.querySelector('#callForm button[type="submit"]');
  UI.setButtonLoading(submitBtn, true, 'Saving...');

  try {
    let res;
    if (id) {
      res = await ApiClient.put(`/api/calls/${id}`, payload);
    } else {
      res = await ApiClient.post('/api/calls', payload);
    }

    if (res.success) {
      UI.showToast(id ? 'Call log updated successfully!' : 'Call scheduled successfully!', 'success');
      UI.closeModal('callModal');
      loadCalls();
    } else {
      UI.showToast(res.error || 'Operation failed', 'danger');
    }
  } catch (err) {
    UI.showToast('Network error while saving call', 'danger');
  } finally {
    UI.setButtonLoading(submitBtn, false);
  }
}

async function deleteCall(id) {
  const confirmed = await UI.confirm({
    title: 'Delete Call Record',
    message: 'Are you sure you want to delete this call interaction record?',
    confirmText: 'Delete Call',
    isDanger: true
  });
  if (!confirmed) return;

  const res = await ApiClient.delete(`/api/calls/${id}`);
  if (res.success) {
    UI.showToast('Call log deleted successfully', 'success');
    loadCalls();
  } else {
    UI.showToast(res.error || 'Failed to delete call', 'danger');
  }
}
