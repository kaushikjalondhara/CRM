/**
 * CRM Profile & Account Management
 * Handles user profile viewing, personal details editing, password updates,
 * avatar uploads, and login history audits.
 */

document.addEventListener('DOMContentLoaded', () => {
  loadProfile();
  initProfileForms();
});

async function loadProfile() {
  try {
    const res = await ApiClient.get('/api/users/profile');
    if (!res.success || !res.data || !res.data.profile) {
      UI.showToast(res.message || 'Failed to load user profile', 'danger');
      return;
    }

    const p = res.data.profile;

    // Header & Summary
    document.getElementById('profileFullName').textContent = `${p.first_name || ''} ${p.last_name || ''}`.trim() || p.email;
    document.getElementById('profileEmailDisplay').textContent = p.email;
    document.getElementById('profileRoleBadge').textContent = p.role || 'Staff';
    document.getElementById('profileStatusBadge').textContent = p.status ? p.status.toUpperCase() : 'ACTIVE';
    document.getElementById('profileStatusBadge').className = `badge ${p.status === 'active' ? 'badge-success' : 'badge-secondary'}`;

    document.getElementById('profileCreatedAt').textContent = UI.formatDate(p.created_at);
    document.getElementById('profileLastLogin').textContent = p.last_login ? UI.formatDateTime(p.last_login) : 'Current session';

    // Avatar
    const avatarImg = document.getElementById('profileAvatarImg');
    const avatarPlaceholder = document.getElementById('profileAvatarPlaceholder');
    if (p.profile_image) {
      avatarImg.src = p.profile_image;
      avatarImg.style.display = 'block';
      avatarPlaceholder.style.display = 'none';
    } else {
      const initial = (p.first_name || p.email || 'U')[0].toUpperCase();
      avatarPlaceholder.textContent = initial;
      avatarPlaceholder.style.display = 'flex';
      avatarImg.style.display = 'none';
    }

    // Populate Info Form
    document.getElementById('profileFirstName').value = p.first_name || '';
    document.getElementById('profileLastName').value = p.last_name || '';
    document.getElementById('profileEmail').value = p.email || '';
    document.getElementById('profilePhone').value = p.phone || '';

    // Permissions chips
    const permList = document.getElementById('profilePermissionsList');
    if (permList) {
      const perms = p.permissions || [];
      if (perms.length === 0) {
        permList.innerHTML = '<span style="font-size:0.75rem; color:var(--text-muted);">Standard permissions</span>';
      } else {
        permList.innerHTML = perms.map(item => `
          <span class="badge badge-secondary" style="font-size: 0.68rem; padding: 2px 6px;">${UI.escapeHtml(item)}</span>
        `).join('');
      }
    }

    // Login History
    const historyBody = document.getElementById('loginHistoryBody');
    if (historyBody) {
      const history = p.login_history || [];
      if (history.length === 0) {
        historyBody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 20px;">No recorded login sessions</td></tr>';
      } else {
        historyBody.innerHTML = history.map(h => `
          <tr>
            <td style="font-size: 0.8rem; white-space: nowrap;">${UI.formatDateTime(h.created_at)}</td>
            <td style="font-family: monospace; font-size: 0.8rem;">${UI.escapeHtml(h.ip_address || '127.0.0.1')}</td>
            <td style="font-size: 0.78rem; color: var(--text-muted); max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${UI.escapeHtml(h.user_agent || '')}">
              ${UI.escapeHtml(h.user_agent || 'Browser')}
            </td>
            <td>
              <span class="badge ${h.status === 'success' ? 'badge-success' : 'badge-danger'}" style="font-size: 0.7rem;">
                ${UI.escapeHtml(h.status ? h.status.toUpperCase() : 'SUCCESS')}
              </span>
            </td>
          </tr>
        `).join('');
      }
    }

  } catch (err) {
    console.error('Profile loading error:', err);
    UI.showToast('Network error loading profile', 'danger');
  }
}

function initProfileForms() {
  // 1. Personal details form
  document.getElementById('profileInfoForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('saveProfileBtn');
    UI.setButtonLoading(btn, true, 'Saving...');

    const payload = {
      first_name: document.getElementById('profileFirstName').value.trim(),
      last_name: document.getElementById('profileLastName').value.trim(),
      email: document.getElementById('profileEmail').value.trim(),
      phone: document.getElementById('profilePhone').value.trim()
    };

    try {
      const res = await ApiClient.put('/api/users/profile', payload);
      if (res.success) {
        UI.showToast('Profile information updated successfully!', 'success');
        loadProfile();
      } else {
        UI.showToast(res.message || 'Failed to update profile', 'danger');
      }
    } catch (err) {
      UI.showToast('Error updating profile', 'danger');
    } finally {
      UI.setButtonLoading(btn, false);
    }
  });

  // 2. Password change form
  document.getElementById('profilePasswordForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const oldPassword = document.getElementById('oldPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;

    if (newPassword !== confirmPassword) {
      UI.showToast('New passwords do not match', 'warning');
      return;
    }

    const btn = document.getElementById('savePasswordBtn');
    UI.setButtonLoading(btn, true, 'Updating...');

    try {
      const res = await ApiClient.put('/api/users/profile/password', {
        old_password: oldPassword,
        new_password: newPassword
      });

      if (res.success) {
        UI.showToast('Password updated successfully!', 'success');
        document.getElementById('profilePasswordForm').reset();
      } else {
        UI.showToast(res.message || 'Failed to update password', 'danger');
      }
    } catch (err) {
      UI.showToast('Error updating password', 'danger');
    } finally {
      UI.setButtonLoading(btn, false);
    }
  });

  // 3. Avatar file input change
  document.getElementById('avatarUploadInput')?.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('photo', file);

    UI.showToast('Uploading profile image...', 'info');

    try {
      const res = await ApiClient.post('/api/users/profile/photo', formData);
      if (res.success && res.data) {
        UI.showToast('Profile picture updated!', 'success');
        loadProfile();
      } else {
        UI.showToast(res.message || 'Failed to upload photo', 'danger');
      }
    } catch (err) {
      UI.showToast('Error uploading photo', 'danger');
    }
  });
}
