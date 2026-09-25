/**
 * CRM Users and Role Permissions Module
 * Handles employee directory, user CRUD, and RBAC matrix configuration.
 */

let currentPage = 1;
let currentTotalPages = 1;
let cachedRoles = [];
let allPermissions = [];
let groupedPermissions = {};
let currentRoleId = null;

document.addEventListener('DOMContentLoaded', async () => {
  const user = await Auth.requireAuth();
  if (!user) return;

  UI.updateNotificationBadge();
  setupEventListeners();

  // If user is not admin, hide the Roles & Permissions matrix tab
  if (user.role !== 'Admin') {
    const matrixBtn = document.getElementById('rolesMatrixTabBtn');
    if (matrixBtn) matrixBtn.style.display = 'none';
  }

  loadUsers();
});

function setupEventListeners() {
  document.getElementById('addUserBtn')?.addEventListener('click', openAddUserModal);

  document.getElementById('searchInput')?.addEventListener('input', debounce(() => {
    currentPage = 1;
    loadUsers();
  }, 350));

  document.getElementById('roleFilter')?.addEventListener('change', () => {
    currentPage = 1;
    loadUsers();
  });

  document.getElementById('statusFilter')?.addEventListener('change', () => {
    currentPage = 1;
    loadUsers();
  });

  document.getElementById('clearFiltersBtn')?.addEventListener('click', () => {
    document.getElementById('searchInput').value = '';
    document.getElementById('roleFilter').value = '';
    document.getElementById('statusFilter').value = '';
    currentPage = 1;
    loadUsers();
  });

  document.getElementById('prevPageBtn')?.addEventListener('click', () => {
    if (currentPage > 1) {
      currentPage--;
      loadUsers();
    }
  });

  document.getElementById('nextPageBtn')?.addEventListener('click', () => {
    if (currentPage < currentTotalPages) {
      currentPage++;
      loadUsers();
    }
  });

  document.getElementById('userForm')?.addEventListener('submit', handleUserSubmit);

  document.getElementById('roleSelect')?.addEventListener('change', (e) => {
    currentRoleId = parseInt(e.target.value);
    loadRolePermissions(currentRoleId);
  });

  document.getElementById('savePermissionsBtn')?.addEventListener('click', handleSavePermissions);
}

function switchUserTab(panelId, btn) {
  document.querySelectorAll('.user-tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.user-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(panelId)?.classList.add('active');

  if (panelId === 'rolesMatrixPanel') {
    initRolesMatrix();
  }
}

async function loadUsers() {
  const tbody = document.getElementById('usersTableBody');
  if (!tbody) return;

  const search = document.getElementById('searchInput')?.value.trim() || '';
  const roleId = document.getElementById('roleFilter')?.value || '';
  const status = document.getElementById('statusFilter')?.value || '';

  const params = new URLSearchParams({
    page: currentPage,
    per_page: 15
  });
  if (search) params.append('search', search);
  if (roleId) params.append('role_id', roleId);
  if (status) params.append('status', status);

  try {
    const res = await ApiClient.get(`/api/users?${params.toString()}`);
    if (!res.success) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #e53e3e; padding: 24px;">Failed to load users: ${UI.escapeHtml(res.data?.message || 'Server error')}</td></tr>`;
      return;
    }

    const { users, roles, total, page, total_pages } = res.data.data;
    currentPage = page;
    currentTotalPages = total_pages || 1;
    cachedRoles = roles || [];

    // Populate role filter dropdown if empty
    populateRoleDropdowns(cachedRoles);

    document.getElementById('paginationInfo').textContent = `Showing ${users.length} of ${total} employees (Page ${page} of ${currentTotalPages})`;
    document.getElementById('prevPageBtn').disabled = currentPage <= 1;
    document.getElementById('nextPageBtn').disabled = currentPage >= currentTotalPages;

    if (users.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; padding: 48px 16px;">
            <div style="font-size: 2.5rem; margin-bottom: 8px;">👤</div>
            <div style="font-weight: 600; font-size: 1.1rem; color: #2d3748;">No Employees Found</div>
            <p style="color: #718096; margin-top: 4px;">Click "+ Add Employee" to create a user account.</p>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = users.map(u => {
      let roleBadge = '<span class="status-badge" style="background: #edf2f7; color: #4a5568;">' + UI.escapeHtml(u.role) + '</span>';
      if (u.role === 'Admin') roleBadge = '<span class="status-badge" style="background: #feebc8; color: #7b341e; border: 1px solid #fbd38d;">Admin</span>';
      else if (u.role === 'Manager') roleBadge = '<span class="status-badge" style="background: #ebf8ff; color: #2b6cb0; border: 1px solid #bee3f8;">Manager</span>';
      else if (u.role === 'Sales Employee') roleBadge = '<span class="status-badge" style="background: #e6fffa; color: #234e52; border: 1px solid #b2f5ea;">Sales</span>';

      let statusBadge = '<span class="status-badge" style="background: #e6fffa; color: #234e52;">Active</span>';
      if (u.status === 'inactive') statusBadge = '<span class="status-badge" style="background: #edf2f7; color: #718096;">Inactive</span>';
      else if (u.status === 'suspended') statusBadge = '<span class="status-badge" style="background: #fff5f5; color: #c53030;">Suspended</span>';

      const isCurrentUser = Auth.getUser() && String(Auth.getUser().id) === String(u.id);

      return `
        <tr>
          <td>
            <div style="display: flex; align-items: center; gap: 10px;">
              <div style="width: 34px; height: 34px; border-radius: 50%; background: #073472; color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.85rem;">
                ${u.first_name ? u.first_name[0] : ''}${u.last_name ? u.last_name[0] : ''}
              </div>
              <div>
                <div style="font-weight: 600; color: #2d3748;">
                  ${UI.escapeHtml(u.name)}
                  ${isCurrentUser ? '<span style="font-size: 0.75rem; background: #e2e8f0; padding: 2px 6px; border-radius: 4px; margin-left: 4px;">You</span>' : ''}
                </div>
              </div>
            </div>
          </td>
          <td>${UI.escapeHtml(u.email)}</td>
          <td>${UI.escapeHtml(u.phone || '—')}</td>
          <td>${roleBadge}</td>
          <td>${statusBadge}</td>
          <td style="font-size: 0.85rem; color: #718096;">${UI.formatDateTime(u.last_login)}</td>
          <td style="text-align: right; white-space: nowrap;">
            <button class="btn btn-secondary btn-sm" onclick="openEditUserModal(${u.id})">Edit</button>
            ${!isCurrentUser ? `
              <button class="btn btn-${u.status === 'active' ? 'secondary' : 'primary'} btn-sm" style="margin-left: 4px;" onclick="toggleUserStatus(${u.id}, '${u.status === 'active' ? 'inactive' : 'active'}')">
                ${u.status === 'active' ? 'Deactivate' : 'Activate'}
              </button>
            ` : ''}
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load users', err);
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #e53e3e; padding: 24px;">An unexpected error occurred.</td></tr>`;
  }
}

function populateRoleDropdowns(roles) {
  const roleFilter = document.getElementById('roleFilter');
  const userRole = document.getElementById('userRole');

  if (roleFilter && roleFilter.options.length <= 1) {
    roles.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r.id;
      opt.textContent = r.name;
      roleFilter.appendChild(opt);
    });
  }

  if (userRole && userRole.options.length === 0) {
    roles.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r.id;
      opt.textContent = r.name;
      userRole.appendChild(opt);
    });
  }
}

function openAddUserModal() {
  document.getElementById('userForm').reset();
  document.getElementById('userId').value = '';
  document.getElementById('userModalTitle').textContent = 'Add New Employee';
  document.getElementById('userPassword').required = true;
  document.getElementById('passwordLabel').textContent = 'Password *';
  document.getElementById('passwordHelp').style.display = 'none';

  populateRoleDropdowns(cachedRoles);
  UI.openModal('userModal');
}

async function openEditUserModal(userId) {
  try {
    const res = await ApiClient.get(`/api/users/${userId}`);
    if (!res.success) {
      UI.showToast('Could not load user details', 'danger');
      return;
    }
    const u = res.data.user;

    document.getElementById('userId').value = u.id;
    document.getElementById('userModalTitle').textContent = `Edit Employee: ${u.first_name} ${u.last_name}`;
    document.getElementById('userFirstName').value = u.first_name;
    document.getElementById('userLastName').value = u.last_name;
    document.getElementById('userEmail').value = u.email;
    document.getElementById('userPhone').value = u.phone || '';
    document.getElementById('userRole').value = u.role_id;
    document.getElementById('userStatus').value = u.status;

    document.getElementById('userPassword').value = '';
    document.getElementById('userPassword').required = false;
    document.getElementById('passwordLabel').textContent = 'Change Password';
    document.getElementById('passwordHelp').style.display = 'block';

    UI.openModal('userModal');
  } catch (err) {
    UI.showToast('Error opening edit user modal', 'danger');
  }
}

async function handleUserSubmit(e) {
  e.preventDefault();
  const id = document.getElementById('userId').value;
  const isEdit = Boolean(id);

  const payload = {
    first_name: document.getElementById('userFirstName').value.trim(),
    last_name: document.getElementById('userLastName').value.trim(),
    email: document.getElementById('userEmail').value.trim(),
    phone: document.getElementById('userPhone').value.trim() || undefined,
    role_id: parseInt(document.getElementById('userRole').value),
    status: document.getElementById('userStatus').value
  };

  const pw = document.getElementById('userPassword').value;
  if (pw && pw.trim().length > 0) {
    payload.password = pw.trim();
  }

  const btn = document.getElementById('saveUserBtn');
  btn.disabled = true;
  btn.textContent = 'Saving...';

  try {
    let res;
    if (isEdit) {
      res = await ApiClient.put(`/api/users/${id}`, payload);
    } else {
      res = await ApiClient.post('/api/users', payload);
    }

    if (res.success) {
      UI.showToast(isEdit ? 'User updated successfully' : 'User created successfully', 'success');
      UI.closeModal('userModal');
      loadUsers();
    } else {
      UI.showToast(res.data?.message || 'Failed to save user', 'danger');
    }
  } catch (err) {
    UI.showToast('Error saving user', 'danger');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save Employee';
  }
}

async function toggleUserStatus(userId, newStatus) {
  try {
    const res = await ApiClient.put(`/api/users/${userId}/status`, { status: newStatus });
    if (res.success) {
      UI.showToast(`User status set to ${newStatus}`, 'success');
      loadUsers();
    } else {
      UI.showToast(res.data?.message || 'Failed to update user status', 'danger');
    }
  } catch (err) {
    UI.showToast('Error toggling status', 'danger');
  }
}

// -------------------------------------------------------------
// Roles & Permissions Matrix
// -------------------------------------------------------------

async function initRolesMatrix() {
  const roleSelect = document.getElementById('roleSelect');
  const container = document.getElementById('permissionMatrixContainer');

  try {
    const [rolesRes, permsRes] = await Promise.all([
      ApiClient.get('/api/roles'),
      ApiClient.get('/api/permissions')
    ]);

    if (!rolesRes.success || !permsRes.success) {
      container.innerHTML = '<div style="color: #e53e3e; text-align: center;">Failed to load permissions system.</div>';
      return;
    }

    const roles = rolesRes.data.roles;
    allPermissions = permsRes.data.permissions;
    groupedPermissions = permsRes.data.grouped_permissions;

    roleSelect.innerHTML = roles.map(r => `<option value="${r.id}">${UI.escapeHtml(r.name)} (${r.permission_count} permissions)</option>`).join('');

    currentRoleId = roles[0]?.id;
    if (currentRoleId) {
      loadRolePermissions(currentRoleId);
    }

  } catch (err) {
    console.error('Failed to init roles matrix', err);
  }
}

async function loadRolePermissions(roleId) {
  const container = document.getElementById('permissionMatrixContainer');
  container.innerHTML = '<div style="text-align: center; padding: 32px; color: #718096;">Loading assigned permissions...</div>';

  try {
    const res = await ApiClient.get(`/api/roles/${roleId}/permissions`);
    if (!res.success) {
      container.innerHTML = '<div style="color: #e53e3e; text-align: center;">Could not load role permissions.</div>';
      return;
    }

    const assignedIds = new Set(res.data.permission_ids || []);
    const isSuperAdmin = res.data.role.name === 'Admin';

    let html = '';
    for (const [moduleName, perms] of Object.entries(groupedPermissions)) {
      html += `
        <div class="permission-group-card">
          <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">
            <h4 style="margin: 0; text-transform: uppercase; font-size: 0.85rem; color: #073472; letter-spacing: 0.5px;">${UI.escapeHtml(moduleName)} Module</h4>
            <span style="font-size: 0.8rem; color: #718096;">${perms.length} actions</span>
          </div>
          <div class="permission-checkbox-grid">
            ${perms.map(p => `
              <label class="permission-item">
                <input type="checkbox" value="${p.id}" class="perm-checkbox" ${assignedIds.has(p.id) ? 'checked' : ''} ${isSuperAdmin ? 'disabled title="Admin retains full permissions"' : ''}>
                <span>${UI.escapeHtml(p.description || p.name)}</span>
              </label>
            `).join('')}
          </div>
        </div>
      `;
    }

    container.innerHTML = html;

  } catch (err) {
    console.error('Failed to load role permissions', err);
  }
}

async function handleSavePermissions() {
  if (!currentRoleId) return;
  const checkboxes = document.querySelectorAll('.perm-checkbox:checked');
  const ids = Array.from(checkboxes).map(cb => parseInt(cb.value));

  const btn = document.getElementById('savePermissionsBtn');
  btn.disabled = true;
  btn.textContent = 'Saving...';

  try {
    const res = await ApiClient.put(`/api/roles/${currentRoleId}/permissions`, { permission_ids: ids });
    if (res.success) {
      UI.showToast(res.data?.message || 'Permissions updated successfully', 'success');
      initRolesMatrix();
    } else {
      UI.showToast(res.data?.message || 'Failed to update permissions', 'danger');
    }
  } catch (err) {
    UI.showToast('Error saving permissions', 'danger');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save Changes';
  }
}

function debounce(fn, delay) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}
