/**
 * CRM Meetings Management Module
 * Handles meeting scheduling, time validation (start_time < end_time), status updates, and meeting logs.
 */

let currentMeetingStatusFilter = '';

document.addEventListener('DOMContentLoaded', async () => {
  if (typeof Auth !== 'undefined') {
    const user = await Auth.requireAuth();
    if (!user) return;
  }

  loadMeetings();
  initMeetingEvents();
});

function initMeetingEvents() {
  const statusFilter = document.getElementById('meetingStatusFilter');
  if (statusFilter) {
    statusFilter.addEventListener('change', (e) => {
      currentMeetingStatusFilter = e.target.value;
      loadMeetings();
    });
  }

  const addBtn = document.getElementById('addMeetingBtn');
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      resetMeetingForm();
      document.getElementById('meetingModalTitle').textContent = 'Schedule New Meeting';
      UI.loadAssignees('meetingUserId');
      UI.openModal('meetingModal');
    });
  }

  const form = document.getElementById('meetingForm');
  if (form) {
    form.addEventListener('submit', handleMeetingFormSubmit);
  }
}

async function loadMeetings() {
  const tbody = document.getElementById('meetingTableBody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 24px; color: var(--text-muted);">Loading meetings...</td></tr>';

  const params = new URLSearchParams();
  if (currentMeetingStatusFilter) params.append('status', currentMeetingStatusFilter);

  try {
    const res = await ApiClient.get(`/api/meetings?${params.toString()}`);
    if (!res.success || !res.data) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 24px; color: var(--danger);">${UI.escapeHtml(res.error || 'Failed to load meetings')}</td></tr>`;
      return;
    }

    const meetings = res.data.meetings || [];
    if (meetings.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7">
            <div class="empty-state">
              <div class="empty-state-icon">📅</div>
              <div class="empty-state-text">No meetings found</div>
              <div class="empty-state-subtext">Schedule a presentation, product demo, or client review meeting.</div>
            </div>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = meetings.map(m => {
      let statusBadge = 'badge-secondary';
      if (m.status === 'completed') statusBadge = 'badge-success';
      else if (m.status === 'scheduled') statusBadge = 'badge-primary';
      else if (m.status === 'cancelled') statusBadge = 'badge-danger';

      const host = m.user_first_name ? `${UI.escapeHtml(m.user_first_name)} ${UI.escapeHtml(m.user_last_name || '')}` : 'User';
      const contactInfo = m.contact_type ? `${m.contact_type.toUpperCase()} #${m.contact_id || '—'}` : 'Direct';

      return `
        <tr>
          <td>
            <strong>${UI.escapeHtml(m.title)}</strong>
            ${m.notes ? `<div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;">${UI.escapeHtml(m.notes)}</div>` : ''}
          </td>
          <td><span class="badge badge-info">${contactInfo}</span></td>
          <td><span class="badge ${statusBadge}">${UI.escapeHtml(m.status)}</span></td>
          <td>${UI.formatDateTime(m.start_time)}</td>
          <td>${UI.formatDateTime(m.end_time)}</td>
          <td>${UI.escapeHtml(m.location || 'Online')}</td>
          <td>
            <div class="table-actions">
              <button class="action-btn" onclick="editMeeting(${m.id})" title="Edit Meeting">✏ Edit</button>
              <button class="action-btn btn-danger" onclick="deleteMeeting(${m.id})" title="Delete Meeting">🗑</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load meetings:', err);
  }
}

function resetMeetingForm() {
  const form = document.getElementById('meetingForm');
  if (form) form.reset();
  document.getElementById('meetingId').value = '';
}

async function editMeeting(id) {
  try {
    const res = await ApiClient.get(`/api/meetings/${id}`);
    if (!res.success || !res.data || !res.data.meeting) {
      UI.showToast(res.error || 'Failed to load meeting', 'danger');
      return;
    }

    const m = res.data.meeting;
    document.getElementById('meetingId').value = m.id;
    document.getElementById('meetingTitle').value = m.title || '';
    document.getElementById('meetingContactType').value = m.contact_type || 'customer';
    document.getElementById('meetingContactId').value = m.contact_id || '';
    document.getElementById('meetingStatus').value = m.status || 'scheduled';
    document.getElementById('meetingStartTime').value = m.start_time ? m.start_time.slice(0, 16) : '';
    document.getElementById('meetingEndTime').value = m.end_time ? m.end_time.slice(0, 16) : '';
    document.getElementById('meetingLocation').value = m.location || '';
    document.getElementById('meetingNotes').value = m.notes || '';

    await UI.loadAssignees('meetingUserId', m.user_id);

    document.getElementById('meetingModalTitle').textContent = 'Edit Meeting';
    UI.openModal('meetingModal');
  } catch (err) {
    UI.showToast('Error fetching meeting details', 'danger');
  }
}

async function handleMeetingFormSubmit(e) {
  e.preventDefault();

  const id = document.getElementById('meetingId').value;
  const startTime = document.getElementById('meetingStartTime').value;
  const endTime = document.getElementById('meetingEndTime').value;

  if (new Date(endTime) <= new Date(startTime)) {
    UI.showToast('End time must be later than start time.', 'warning');
    return;
  }

  const payload = {
    title: document.getElementById('meetingTitle').value.trim(),
    contact_type: document.getElementById('meetingContactType').value || null,
    contact_id: parseInt(document.getElementById('meetingContactId').value) || null,
    status: document.getElementById('meetingStatus').value,
    start_time: startTime,
    end_time: endTime,
    location: document.getElementById('meetingLocation').value.trim(),
    notes: document.getElementById('meetingNotes').value.trim(),
    user_id: document.getElementById('meetingUserId').value || null,
  };

  if (!payload.title || !payload.start_time || !payload.end_time) {
    UI.showToast('Meeting title, start time, and end time are required.', 'warning');
    return;
  }

  const submitBtn = document.querySelector('#meetingForm button[type="submit"]');
  UI.setButtonLoading(submitBtn, true, 'Saving...');

  try {
    let res;
    if (id) {
      res = await ApiClient.put(`/api/meetings/${id}`, payload);
    } else {
      res = await ApiClient.post('/api/meetings', payload);
    }

    if (res.success) {
      UI.showToast(id ? 'Meeting updated successfully!' : 'Meeting scheduled successfully!', 'success');
      UI.closeModal('meetingModal');
      loadMeetings();
    } else {
      UI.showToast(res.error || 'Operation failed', 'danger');
    }
  } catch (err) {
    UI.showToast('Network error while saving meeting', 'danger');
  } finally {
    UI.setButtonLoading(submitBtn, false);
  }
}

async function deleteMeeting(id) {
  const confirmed = await UI.confirm({
    title: 'Delete Meeting',
    message: 'Are you sure you want to cancel and delete this scheduled meeting?',
    confirmText: 'Delete Meeting',
    isDanger: true
  });
  if (!confirmed) return;

  const res = await ApiClient.delete(`/api/meetings/${id}`);
  if (res.success) {
    UI.showToast('Meeting deleted successfully', 'success');
    loadMeetings();
  } else {
    UI.showToast(res.error || 'Failed to delete meeting', 'danger');
  }
}
