/**
 * CRM Settings Module
 * Handles loading and updating company profiles, localization, and invoicing parameters.
 */

document.addEventListener('DOMContentLoaded', async () => {
  const user = await Auth.requireAuth();
  if (!user) return;

  UI.updateNotificationBadge();
  setupEventListeners();
  loadSettings();
  loadBackups();
  initBackupHandlers();
});

function setupEventListeners() {
  document.getElementById('settingsForm')?.addEventListener('submit', handleSettingsSubmit);

  document.getElementById('currencyCode')?.addEventListener('change', (e) => {
    const code = e.target.value;
    const symbolInp = document.getElementById('currencySymbol');
    if (code === 'INR') symbolInp.value = '₹';
    else if (code === 'USD') symbolInp.value = '$';
    else if (code === 'EUR') symbolInp.value = '€';
    else if (code === 'GBP') symbolInp.value = '£';
  });
}

let backupsCache = [];

function initBackupHandlers() {
  document.getElementById('btnCreateBackup')?.addEventListener('click', async () => {
    const btn = document.getElementById('btnCreateBackup');
    UI.setButtonLoading(btn, true, 'Dumping database...');

    try {
      const res = await ApiClient.post('/api/backup/create');
      if (res.success) {
        UI.showToast('Database snapshot created successfully!', 'success');
        loadBackups();
      } else {
        UI.showToast(res.message || 'Failed to generate backup', 'danger');
      }
    } catch (err) {
      UI.showToast('Error generating backup', 'danger');
    } finally {
      UI.setButtonLoading(btn, false);
    }
  });

  document.getElementById('restoreBackupForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const backupId = document.getElementById('restoreBackupId').value;
    const code = document.getElementById('confirmRestoreCode').value.trim();

    if (code !== 'RESTORE') {
      UI.showToast('Please type RESTORE exactly to confirm', 'warning');
      return;
    }

    const btn = document.getElementById('confirmRestoreBtn');
    UI.setButtonLoading(btn, true, 'Restoring database...');

    try {
      const res = await ApiClient.post(`/api/backup/${backupId}/restore`, { confirmation_code: code });
      if (res.success) {
        UI.showToast('Database successfully restored from snapshot!', 'success');
        UI.closeModal('restoreBackupModal');
        document.getElementById('restoreBackupForm').reset();
        setTimeout(() => window.location.reload(), 1500);
      } else {
        UI.showToast(res.message || 'Restore failed', 'danger');
      }
    } catch (err) {
      UI.showToast('Error during database restoration', 'danger');
    } finally {
      UI.setButtonLoading(btn, false);
    }
  });
}

async function loadBackups() {
  const tbody = document.getElementById('backupsTableBody');
  if (!tbody) return;

  try {
    const res = await ApiClient.get('/api/backup/list');
    if (!res.success || !res.data) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">Backup feature is restricted to Admin role.</td></tr>';
      return;
    }

    const backups = res.data.backups || [];
    backupsCache = backups;

    if (backups.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">No database backups created yet. Click "+ Create Backup Now" to create your first archive.</td></tr>';
      return;
    }

    tbody.innerHTML = backups.map((b, idx) => {
      const sizeStr = b.file_size ? `${(b.file_size / 1024).toFixed(1)} KB` : '—';
      const statusBadge = b.status === 'completed'
        ? '<span class="badge badge-success">READY</span>'
        : `<span class="badge badge-warning">${UI.escapeHtml(b.status || 'PENDING')}</span>`;

      return `
        <tr>
          <td><strong style="font-family: monospace; font-size: 0.85rem;">${UI.escapeHtml(b.file_name)}</strong></td>
          <td>${sizeStr}</td>
          <td style="font-size: 0.8rem; color: var(--text-secondary);">${UI.formatDateTime(b.created_at)}</td>
          <td>${statusBadge}</td>
          <td>
            <div style="display: flex; gap: 6px;">
              <a href="${ApiClient.baseUrl}/api/backup/${b.id}/download?token=${encodeURIComponent(ApiClient.getToken())}"
                 class="btn btn-outline btn-sm" style="padding: 2px 8px; font-size: 0.75rem;" download title="Download SQL Dump">
                💾 Download SQL
              </a>
              <button type="button" class="btn btn-danger btn-sm" onclick="promptRestoreBackup(${idx})" style="padding: 2px 8px; font-size: 0.75rem;" title="Restore Live Database">
                ⚠️ Restore
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--danger); padding: 20px;">Error loading backups</td></tr>';
  }
}

function promptRestoreBackup(idx) {
  const b = backupsCache[idx];
  if (!b) return;

  document.getElementById('restoreBackupId').value = b.id;
  document.getElementById('restoreBackupFilename').textContent = b.file_name;
  document.getElementById('confirmRestoreCode').value = '';
  UI.openModal('restoreBackupModal');
}

if (typeof window !== 'undefined') {
  window.promptRestoreBackup = promptRestoreBackup;
}

