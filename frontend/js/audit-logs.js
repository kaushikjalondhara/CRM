/**
 * CRM Audit Logs Management
 * Filterable immutable compliance viewer.
 */

let currentAuditPage = 1;
let currentAuditFilters = {};
let currentLogs = [];

document.addEventListener('DOMContentLoaded', () => {
  initAuditLogs();
});

function initAuditLogs() {
  const form = document.getElementById('auditFilterForm');
  form?.addEventListener('submit', (e) => {
    e.preventDefault();
    currentAuditFilters = {
      entity_type: document.getElementById('filterEntity').value,
      action: document.getElementById('filterAction').value,
      start_date: document.getElementById('filterStartDate').value,
      end_date: document.getElementById('filterEndDate').value
    };
    currentAuditPage = 1;
    loadAuditLogs();
  });

  document.getElementById('btnResetAudit')?.addEventListener('click', () => {
    form.reset();
    currentAuditFilters = {};
    currentAuditPage = 1;
    loadAuditLogs();
  });

  document.getElementById('btnExportAuditCsv')?.addEventListener('click', () => {
    UI.exportData('audit', 'csv', currentAuditFilters);
  });

  loadAuditLogs();
}

async function loadAuditLogs(page = 1) {
  currentAuditPage = page;
  const tbody = document.getElementById('auditLogsBody');
  if (!tbody) return;

  UI.renderTableLoading(tbody, 6, 'Loading audit records...');

  const params = new URLSearchParams({
    page: currentAuditPage,
    per_page: 20,
    ...currentAuditFilters
  });

  // Filter out blanks
  for (const [k, v] of Array.from(params.entries())) {
    if (!v) params.delete(k);
  }

  try {
    const res = await ApiClient.get(`/api/audit-logs?${params.toString()}`);
    if (!res.success || !res.data) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--danger); padding: 30px;">${UI.escapeHtml(res.message || 'Failed to load logs')}</td></tr>`;
      return;
    }

    const logs = res.data.logs || [];
    currentLogs = logs;

    if (logs.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6">
            <div class="empty-state">
              <div class="empty-state-icon">🛡️</div>
              <div class="empty-state-text">No audit logs found</div>
              <div class="empty-state-subtext">No system activity records match your current filter criteria.</div>
            </div>
          </td>
        </tr>
      `;
      renderPagination(0, 1, 20);
      return;
    }

    tbody.innerHTML = logs.map((log, index) => {
      const actor = log.actor_name ? `${log.actor_name} ${log.actor_email ? `<span style="color:var(--text-muted); font-size:0.75rem;">(${log.actor_email})</span>` : ''}` : 'System';
      const actionBadge = getActionBadge(log.action);

      return `
        <tr>
          <td style="font-size: 0.8rem; color: var(--text-secondary); white-space: nowrap;">
            ${UI.formatDateTime(log.created_at)}
          </td>
          <td>${actor}</td>
          <td>
            <span class="badge badge-secondary" style="font-size: 0.75rem;">
              ${UI.escapeHtml(log.entity_type || 'system')} ${log.entity_id ? `#${log.entity_id}` : ''}
            </span>
          </td>
          <td>${actionBadge}</td>
          <td style="font-family: monospace; font-size: 0.8rem; color: var(--text-muted);">
            ${UI.escapeHtml(log.ip_address || '—')}
          </td>
          <td>
            <button class="btn btn-outline btn-sm" onclick="viewAuditDetails(${index})" style="padding: 4px 8px; font-size: 0.75rem;">
              🔍 View
            </button>
          </td>
        </tr>
      `;
    }).join('');

    renderPagination(res.data.total || 0, res.data.page || 1, res.data.per_page || 20);

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--danger); padding: 30px;">Network error loading audit logs</td></tr>`;
  }
}

function getActionBadge(action) {
  const act = (action || '').toUpperCase();
  if (act.includes('CREATE')) return `<span class="badge badge-success">${UI.escapeHtml(act)}</span>`;
  if (act.includes('UPDATE')) return `<span class="badge badge-primary">${UI.escapeHtml(act)}</span>`;
  if (act.includes('DELETE')) return `<span class="badge badge-danger">${UI.escapeHtml(act)}</span>`;
  if (act.includes('LOGIN')) return `<span class="badge badge-warning">${UI.escapeHtml(act)}</span>`;
  if (act.includes('EXPORT')) return `<span class="badge badge-info">${UI.escapeHtml(act)}</span>`;
  return `<span class="badge badge-secondary">${UI.escapeHtml(act)}</span>`;
}

function renderPagination(total, page, perPage) {
  const container = document.getElementById('auditPagination');
  if (!container) return;

  const totalPages = Math.ceil(total / perPage) || 1;
  container.innerHTML = `
    <div style="font-size: 0.8rem; color: var(--text-muted);">
      Showing <strong>${total > 0 ? (page - 1) * perPage + 1 : 0}</strong> to <strong>${Math.min(page * perPage, total)}</strong> of <strong>${total}</strong> records
    </div>
    <div style="display: flex; gap: 6px;">
      <button class="btn btn-outline btn-sm" ${page <= 1 ? 'disabled' : ''} onclick="loadAuditLogs(${page - 1})">◀ Prev</button>
      <span style="font-size: 0.85rem; padding: 6px 10px;">Page ${page} / ${totalPages}</span>
      <button class="btn btn-outline btn-sm" ${page >= totalPages ? 'disabled' : ''} onclick="loadAuditLogs(${page + 1})">Next ▶</button>
    </div>
  `;
}

function viewAuditDetails(index) {
  const log = currentLogs[index];
  if (!log) return;

  const body = document.getElementById('auditDetailBody');
  if (!body) return;

  let oldValFormatted = '—';
  let newValFormatted = '—';

  try {
    if (log.old_values) {
      const parsed = typeof log.old_values === 'string' ? JSON.parse(log.old_values) : log.old_values;
      oldValFormatted = `<pre style="background: #f8fafc; padding: 10px; border-radius: 6px; font-size: 0.75rem; overflow-x: auto; max-height: 180px;">${UI.escapeHtml(JSON.stringify(parsed, null, 2))}</pre>`;
    }
  } catch (e) {
    oldValFormatted = `<pre style="font-size: 0.75rem;">${UI.escapeHtml(String(log.old_values))}</pre>`;
  }

  try {
    if (log.new_values) {
      const parsed = typeof log.new_values === 'string' ? JSON.parse(log.new_values) : log.new_values;
      newValFormatted = `<pre style="background: #f8fafc; padding: 10px; border-radius: 6px; font-size: 0.75rem; overflow-x: auto; max-height: 180px;">${UI.escapeHtml(JSON.stringify(parsed, null, 2))}</pre>`;
    }
  } catch (e) {
    newValFormatted = `<pre style="font-size: 0.75rem;">${UI.escapeHtml(String(log.new_values))}</pre>`;
  }

  body.innerHTML = `
    <div class="form-grid-2" style="margin-bottom: 16px;">
      <div class="info-item">
        <span class="info-label">Action</span>
        <span class="info-value">${getActionBadge(log.action)}</span>
      </div>
      <div class="info-item">
        <span class="info-label">Timestamp</span>
        <span class="info-value">${UI.formatDateTime(log.created_at)}</span>
      </div>
      <div class="info-item">
        <span class="info-label">Entity</span>
        <span class="info-value">${UI.escapeHtml(log.entity_type || 'system')} #${log.entity_id || '—'}</span>
      </div>
      <div class="info-item">
        <span class="info-label">Actor</span>
        <span class="info-value">${UI.escapeHtml(log.actor_name || 'System')}</span>
      </div>
      <div class="info-item">
        <span class="info-label">IP Address</span>
        <span class="info-value" style="font-family: monospace;">${UI.escapeHtml(log.ip_address || '—')}</span>
      </div>
      <div class="info-item">
        <span class="info-label">User Agent</span>
        <span class="info-value" style="font-size: 0.75rem; word-break: break-all;">${UI.escapeHtml(log.user_agent || '—')}</span>
      </div>
    </div>

    <div style="margin-top: 14px;">
      <h4 style="font-size: 0.85rem; font-weight: 700; margin-bottom: 6px; color: var(--text-secondary);">Previous State</h4>
      ${oldValFormatted}
    </div>

    <div style="margin-top: 14px;">
      <h4 style="font-size: 0.85rem; font-weight: 700; margin-bottom: 6px; color: var(--text-secondary);">New State / Data</h4>
      ${newValFormatted}
    </div>
  `;

  UI.openModal('auditDetailModal');
}

if (typeof window !== 'undefined') {
  window.viewAuditDetails = viewAuditDetails;
  window.loadAuditLogs = loadAuditLogs;
}
