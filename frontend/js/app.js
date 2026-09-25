/**
 * CRM Core Application Bootstrap
 * Handles interactive layout controls, sidebar responsiveness, and API health checks.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Apply permission visibility synchronously from cached profile to prevent UI flickers
  if (window.Auth && window.Auth.getUser && window.Auth.applyPermissionVisibility) {
    const cachedUser = window.Auth.getUser();
    if (cachedUser) {
      window.Auth.applyPermissionVisibility(cachedUser);
    }
  }

  initSidebarControls();
  initApiStatusBadge();
  initGlobalSearch();
  UI.updateNotificationBadge();
});

/**
 * Initialize unified global search with instant debounced popup & keyboard navigation
 */
function initGlobalSearch() {
  const searchInputs = document.querySelectorAll('.search-box input, header input[placeholder*="Search"]');
  if (!searchInputs.length) return;

  searchInputs.forEach(input => {
    const parent = input.closest('.search-box') || input.parentElement;
    parent.classList.add('global-search-container');

    let dropdown = parent.querySelector('.search-results-dropdown');
    if (!dropdown) {
      dropdown = document.createElement('div');
      dropdown.className = 'search-results-dropdown';
      parent.appendChild(dropdown);
    }

    let debounceTimer = null;
    let selectedIndex = -1;

    input.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      const query = input.value.trim();
      if (query.length < 2) {
        dropdown.classList.remove('active');
        dropdown.innerHTML = '';
        return;
      }

      dropdown.innerHTML = '<div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 0.85rem;"><span class="btn-spinner" style="width:16px;height:16px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:6px;"></span> Searching CRM...</div>';
      dropdown.classList.add('active');

      debounceTimer = setTimeout(async () => {
        try {
          const res = await ApiClient.get(`/api/search?q=${encodeURIComponent(query)}`);
          if (!res.success || !res.data || !res.data.results || Object.keys(res.data.results).length === 0) {
            dropdown.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 0.85rem;">No results found for "${UI.escapeHtml(query)}"</div>`;
            return;
          }

          const results = res.data.results;
          let html = '';
          const categoryIcons = {
            customers: '👥 Customers',
            leads: '🎯 Leads',
            deals: '💼 Deals',
            invoices: '🧾 Invoices',
            tasks: '✅ Tasks',
            calls: '📞 Calls',
            meetings: '📅 Meetings',
            products: '📦 Products',
            users: '👤 Users'
          };

          for (const [cat, items] of Object.entries(results)) {
            if (!items || !items.length) continue;
            const catLabel = categoryIcons[cat] || cat.toUpperCase();
            html += `<div class="search-category-group">`;
            html += `<div class="search-category-title">${catLabel} (${items.length})</div>`;
            items.forEach(item => {
              html += `
                <a href="${item.url}" class="search-item">
                  <div class="search-item-main">
                    <span class="search-item-title">${UI.escapeHtml(item.title)}</span>
                    ${item.subtitle ? `<span class="search-item-sub">${UI.escapeHtml(item.subtitle)}</span>` : ''}
                  </div>
                  <span class="badge badge-secondary" style="font-size: 0.7rem;">${cat}</span>
                </a>
              `;
            });
            html += `</div>`;
          }

          dropdown.innerHTML = html;
          selectedIndex = -1;
        } catch (err) {
          dropdown.innerHTML = '<div style="padding: 14px; text-align: center; color: var(--danger); font-size: 0.85rem;">Search failed</div>';
        }
      }, 250);
    });

    input.addEventListener('keydown', (e) => {
      const items = dropdown.querySelectorAll('.search-item');
      if (!dropdown.classList.contains('active') || !items.length) {
        if (e.key === 'Escape') dropdown.classList.remove('active');
        return;
      }

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedIndex = (selectedIndex + 1) % items.length;
        updateHighlight(items);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIndex = (selectedIndex - 1 + items.length) % items.length;
        updateHighlight(items);
      } else if (e.key === 'Enter') {
        if (selectedIndex >= 0 && items[selectedIndex]) {
          e.preventDefault();
          items[selectedIndex].click();
        }
      } else if (e.key === 'Escape') {
        dropdown.classList.remove('active');
      }
    });

    function updateHighlight(items) {
      items.forEach((it, idx) => {
        if (idx === selectedIndex) {
          it.classList.add('highlighted');
          it.scrollIntoView({ block: 'nearest' });
        } else {
          it.classList.remove('highlighted');
        }
      });
    }

    // Close on click outside
    document.addEventListener('click', (e) => {
      if (!parent.contains(e.target)) {
        dropdown.classList.remove('active');
      }
    });
  });

  // Global keyboard shortcut Ctrl+K / Cmd+K
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      const firstInput = searchInputs[0];
      if (firstInput) {
        firstInput.focus();
        firstInput.select();
      }
    }
  });
}


/**
 * Initialize responsive sidebar drawer interactions
 */
function initSidebarControls() {
  const toggleBtn = document.getElementById('sidebarToggleBtn');
  const sidebar = document.getElementById('crmSidebar');
  const backdrop = document.getElementById('sidebarBackdrop');

  if (!toggleBtn || !sidebar) return;

  function toggleSidebar() {
    sidebar.classList.toggle('open');
    if (backdrop) {
      backdrop.classList.toggle('active');
    }
  }

  function closeSidebar() {
    sidebar.classList.remove('open');
    if (backdrop) {
      backdrop.classList.remove('active');
    }
  }

  toggleBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleSidebar();
  });

  if (backdrop) {
    backdrop.addEventListener('click', closeSidebar);
  }

  // Close sidebar on pressing Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sidebar.classList.contains('open')) {
      closeSidebar();
    }
  });
}

/**
 * Check backend API health check endpoint and update badge if present on the page
 */
async function initApiStatusBadge() {
  const badge = document.getElementById('apiStatusBadge');
  const dot = document.getElementById('apiStatusDot');
  const text = document.getElementById('apiStatusText');

  if (!badge || typeof ApiClient === 'undefined') return;

  try {
    const result = await ApiClient.checkHealth();
    if (result.success && result.data && result.data.success) {
      if (dot) dot.classList.add('online');
      if (text) text.textContent = 'API Online';
    } else {
      if (dot) dot.classList.remove('online');
      if (text) text.textContent = 'API Offline';
    }
  } catch (err) {
    if (dot) dot.classList.remove('online');
    if (text) text.textContent = 'API Unreachable';
  }
}

/**
 * Global CRM UI Utilities
 */
const UI = {
  escapeHtml(str) {
    if (!str && str !== 0) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  },

  formatCurrency(amount) {
    const num = parseFloat(amount) || 0;
    return '₹' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  },

  async updateNotificationBadge() {
    if (typeof ApiClient === 'undefined' || !ApiClient.getToken()) return;
    try {
      const res = await ApiClient.get('/api/notifications/unread-count');
      if (res.success && res.data) {
        const count = res.data.unread_count || 0;
        const badgeEls = document.querySelectorAll('.notification-badge-count');
        badgeEls.forEach(el => {
          if (count > 0) {
            el.textContent = count > 99 ? '99+' : count;
            el.style.display = 'inline-flex';
          } else {
            el.style.display = 'none';
          }
        });
      }
    } catch (e) {
      // silent
    }
  },

  formatDate(dateStr) {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch (e) {
      return dateStr;
    }
  },

  formatDateTime(dateStr) {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      return d.toLocaleString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
    } catch (e) {
      return dateStr;
    }
  },

  showToast(message, type = 'info') {
    let container = document.getElementById('globalToastContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'globalToastContainer';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icon = type === 'success' ? '✓' : type === 'danger' ? '✕' : type === 'warning' ? '⚠' : 'ℹ';
    toast.innerHTML = `<span style="font-weight: bold;">${icon}</span> <span>${this.escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(40px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  },

  openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('active');
    }
  },

  closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('active');
    }
  },

  async loadAssignees(selectElementId, selectedId = null) {
    const sel = document.getElementById(selectElementId);
    if (!sel || typeof ApiClient === 'undefined') return;

    try {
      const res = await ApiClient.get('/api/users/assignable');
      if (res.success && res.data && res.data.users) {
        sel.innerHTML = '<option value="">-- Unassigned --</option>';
        res.data.users.forEach(u => {
          const opt = document.createElement('option');
          opt.value = u.id;
          const fullName = (u.name && u.name.trim()) || `${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email || `User #${u.id}`;
          const roleLabel = u.role ? ` (${u.role})` : '';
          opt.textContent = `${fullName}${roleLabel}`;
          if (selectedId && String(selectedId) === String(u.id)) {
            opt.selected = true;
          }
          sel.appendChild(opt);
        });
      }
    } catch (e) {
      console.warn('Failed to load assignees', e);
    }
  },

  confirm(optionsOrMessage) {
    const opts = typeof optionsOrMessage === 'string'
      ? { message: optionsOrMessage }
      : (optionsOrMessage || {});

    const title = opts.title || 'Confirm Action';
    const message = opts.message || 'Are you sure you want to proceed?';
    const confirmText = opts.confirmText || 'Confirm';
    const cancelText = opts.cancelText || 'Cancel';
    const isDanger = opts.isDanger !== false;

    return new Promise((resolve) => {
      let modal = document.getElementById('globalConfirmModal');
      if (!modal) {
        modal = document.createElement('div');
        modal.id = 'globalConfirmModal';
        modal.className = 'modal';
        modal.innerHTML = `
          <div class="modal-backdrop"></div>
          <div class="modal-dialog" style="max-width: 440px; text-align: left;">
            <div class="modal-header" style="border-bottom: 1px solid var(--border-color); padding: 16px 20px;">
              <h3 id="globalConfirmTitle" class="modal-title" style="font-size: 1.1rem; font-weight: 700; margin: 0;"></h3>
              <button type="button" class="modal-close" id="globalConfirmCloseX">&times;</button>
            </div>
            <div class="modal-body" style="padding: 20px;">
              <p id="globalConfirmMessage" style="color: var(--text-secondary); line-height: 1.5; font-size: 0.95rem; margin: 0;"></p>
            </div>
            <div class="modal-footer" style="padding: 14px 20px; border-top: 1px solid var(--border-color); display: flex; justify-content: flex-end; gap: 10px;">
              <button id="globalConfirmCancelBtn" type="button" class="btn btn-outline btn-sm"></button>
              <button id="globalConfirmOkBtn" type="button" class="btn btn-sm"></button>
            </div>
          </div>
        `;
        document.body.appendChild(modal);
      }

      const titleEl = document.getElementById('globalConfirmTitle');
      const msgEl = document.getElementById('globalConfirmMessage');
      const cancelBtn = document.getElementById('globalConfirmCancelBtn');
      const okBtn = document.getElementById('globalConfirmOkBtn');
      const closeX = document.getElementById('globalConfirmCloseX');
      const backdrop = modal.querySelector('.modal-backdrop');

      titleEl.textContent = title;
      msgEl.textContent = message;
      cancelBtn.textContent = cancelText;
      okBtn.textContent = confirmText;
      okBtn.className = isDanger ? 'btn btn-danger btn-sm' : 'btn btn-primary btn-sm';

      function cleanup(result) {
        modal.classList.remove('active');
        cancelBtn.onclick = null;
        okBtn.onclick = null;
        if (closeX) closeX.onclick = null;
        if (backdrop) backdrop.onclick = null;
        resolve(result);
      }

      cancelBtn.onclick = () => cleanup(false);
      okBtn.onclick = () => cleanup(true);
      if (closeX) closeX.onclick = () => cleanup(false);
      if (backdrop) backdrop.onclick = () => cleanup(false);

      modal.classList.add('active');
    });
  },

  setButtonLoading(btn, isLoading, loadingText = 'Processing...') {
    if (!btn) return;
    if (isLoading) {
      btn.dataset.originalHtml = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = `<span class="btn-spinner"></span> ${this.escapeHtml(loadingText)}`;
    } else {
      btn.disabled = false;
      if (btn.dataset.originalHtml) {
        btn.innerHTML = btn.dataset.originalHtml;
        delete btn.dataset.originalHtml;
      }
    }
  },

  renderTableLoading(tbody, colSpan = 6, message = 'Loading records...') {
    if (!tbody) return;
    tbody.innerHTML = `
      <tr>
        <td colspan="${colSpan}" style="text-align: center; padding: 40px 20px;">
          <div class="btn-spinner" style="width: 22px; height: 22px; border-width: 3px; border-top-color: var(--primary); margin-bottom: 10px;"></div>
          <div style="color: var(--text-muted); font-size: var(--font-size-sm);">${this.escapeHtml(message)}</div>
        </td>
      </tr>
    `;
  },

  renderEmptyState(container, { icon = '📭', title = 'No records found', message = 'No data available to display.', actionText = null, actionCallback = null } = {}) {
    if (!container) return;
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">${icon}</div>
        <div class="empty-state-text" style="font-weight: 600; font-size: 1rem; color: var(--text-primary);">${this.escapeHtml(title)}</div>
        <div class="empty-state-subtext">${this.escapeHtml(message)}</div>
        ${actionText ? `<button class="btn btn-primary btn-sm" style="margin-top: 14px;" id="emptyStateActionBtn">${this.escapeHtml(actionText)}</button>` : ''}
      </div>
    `;
    if (actionText && typeof actionCallback === 'function') {
      const btn = container.querySelector('#emptyStateActionBtn');
      if (btn) btn.onclick = actionCallback;
    }
  },

  print() {
    window.print();
  },

  exportData(moduleName, format = 'csv', filters = {}) {
    const token = typeof ApiClient !== 'undefined' ? ApiClient.getToken() : '';
    const cleanFilters = {};
    for (const [k, v] of Object.entries(filters)) {
      if (v !== undefined && v !== null && v !== '' && v !== 'all') {
        cleanFilters[k] = v;
      }
    }
    const params = new URLSearchParams({ format, token, ...cleanFilters });
    const url = `/api/export/${moduleName}?${params.toString()}`;
    window.open(url, '_blank');
  },

  initBulkSelection({ selectAllId = 'selectAll', rowSelector = '.row-checkbox', toolbarId = 'bulkActionsToolbar', countId = 'bulkSelectedCount', onSelectionChange = null } = {}) {
    const selectAll = document.getElementById(selectAllId);
    const toolbar = document.getElementById(toolbarId);
    const countEl = document.getElementById(countId);

    function getSelectedIds() {
      const checked = document.querySelectorAll(`${rowSelector}:checked`);
      return Array.from(checked).map(cb => cb.value);
    }

    function updateState() {
      const selected = getSelectedIds();
      if (countEl) countEl.textContent = selected.length;
      if (toolbar) {
        if (selected.length > 0) {
          toolbar.classList.add('active');
        } else {
          toolbar.classList.remove('active');
        }
      }
      if (typeof onSelectionChange === 'function') {
        onSelectionChange(selected);
      }
    }

    if (selectAll) {
      selectAll.addEventListener('change', () => {
        const rows = document.querySelectorAll(rowSelector);
        rows.forEach(r => r.checked = selectAll.checked);
        updateState();
      });
    }

    document.addEventListener('change', (e) => {
      if (e.target && e.target.matches(rowSelector)) {
        const rows = document.querySelectorAll(rowSelector);
        const checked = document.querySelectorAll(`${rowSelector}:checked`);
        if (selectAll) {
          selectAll.checked = rows.length > 0 && rows.length === checked.length;
          selectAll.indeterminate = checked.length > 0 && checked.length < rows.length;
        }
        updateState();
      }
    });

    return {
      getSelectedIds,
      clearSelection() {
        const rows = document.querySelectorAll(rowSelector);
        rows.forEach(r => r.checked = false);
        if (selectAll) {
          selectAll.checked = false;
          selectAll.indeterminate = false;
        }
        updateState();
      }
    };
  },

  openImportModal(moduleName, onComplete) {
    const capitalized = moduleName.charAt(0).toUpperCase() + moduleName.slice(1);
    let modal = document.getElementById('globalImportModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'globalImportModal';
      modal.className = 'modal';
      document.body.appendChild(modal);
    }

    const token = typeof ApiClient !== 'undefined' ? ApiClient.getToken() : '';
    let previewData = null;

    modal.innerHTML = `
      <div class="modal-backdrop"></div>
      <div class="modal-dialog modal-lg" style="max-width: 680px; text-align: left;">
        <div class="modal-header">
          <h3 class="modal-title">📥 Bulk Import ${capitalized}</h3>
          <button type="button" class="modal-close" id="importModalCloseX">&times;</button>
        </div>
        <div class="modal-body" style="padding: 20px;">
          <div style="background: var(--bg-secondary); border-radius: var(--radius-md); padding: 14px 16px; margin-bottom: 20px; border: 1px solid var(--border-color);">
            <div style="font-weight: 600; margin-bottom: 6px; font-size: 0.9rem;">Download Sample Template</div>
            <p style="margin: 0 0 10px; font-size: 0.825rem; color: var(--text-muted);">
              Use our pre-formatted templates to ensure headers and columns match expected fields:
            </p>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
              <a href="/api/import/template/${moduleName}?format=csv&token=${token}" class="btn btn-outline btn-sm" download>
                📄 Sample CSV
              </a>
              <a href="/api/import/template/${moduleName}?format=xlsx&token=${token}" class="btn btn-outline btn-sm" download>
                📊 Sample Excel (.xlsx)
              </a>
            </div>
          </div>

          <div class="form-group" style="margin-bottom: 16px;">
            <label class="form-label" style="font-weight: 600;">Upload CSV or Excel File</label>
            <input type="file" id="importFileInput" accept=".csv, .xlsx, .xls" class="form-control" style="padding: 10px;">
            <small style="color: var(--text-muted); font-size: 0.75rem; margin-top: 4px; display: block;">Supported: CSV, XLSX, XLS. Max file size: 10MB.</small>
          </div>

          <div id="importLoadingIndicator" style="display: none; text-align: center; padding: 20px;">
            <div class="btn-spinner" style="width: 24px; height: 24px; border-width: 3px; border-top-color: var(--primary); margin: 0 auto 10px;"></div>
            <div style="color: var(--text-muted); font-size: 0.85rem;">Analyzing file and validating records...</div>
          </div>

          <div id="importPreviewArea" style="display: none;"></div>
        </div>
        <div class="modal-footer" style="display: flex; justify-content: flex-end; gap: 10px; border-top: 1px solid var(--border-color); padding: 14px 20px;">
          <button type="button" class="btn btn-outline btn-sm" id="importModalCancelBtn">Cancel</button>
          <button type="button" class="btn btn-primary btn-sm" id="importModalConfirmBtn" style="display: none;">
            Confirm & Import Records
          </button>
        </div>
      </div>
    `;

    const closeBtn = modal.querySelector('#importModalCloseX');
    const cancelBtn = modal.querySelector('#importModalCancelBtn');
    const confirmBtn = modal.querySelector('#importModalConfirmBtn');
    const backdrop = modal.querySelector('.modal-backdrop');
    const fileInput = modal.querySelector('#importFileInput');
    const loadingEl = modal.querySelector('#importLoadingIndicator');
    const previewArea = modal.querySelector('#importPreviewArea');

    function closeModal() {
      modal.classList.remove('active');
    }

    closeBtn.onclick = closeModal;
    cancelBtn.onclick = closeModal;
    backdrop.onclick = closeModal;

    fileInput.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      loadingEl.style.display = 'block';
      previewArea.style.display = 'none';
      confirmBtn.style.display = 'none';

      const formData = new FormData();
      formData.append('file', file);
      formData.append('module', moduleName);

      try {
        const res = await ApiClient.upload('/api/import/preview', formData);
        loadingEl.style.display = 'none';

        if (!res.success || !res.data) {
          previewArea.innerHTML = `
            <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid var(--danger); border-radius: var(--radius-md); padding: 12px 16px; color: var(--danger); font-size: 0.875rem;">
              <strong>Error reading file:</strong> ${UI.escapeHtml(res.error || res.message || 'Validation failed')}
            </div>
          `;
          previewArea.style.display = 'block';
          return;
        }

        previewData = res.data;
        const validCount = previewData.valid_rows_count || 0;
        const invalidCount = previewData.invalid_rows_count || 0;
        const totalCount = previewData.total_rows || 0;

        let previewHtml = `
          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px;">
            <div style="background: var(--bg-secondary); padding: 12px; border-radius: var(--radius-sm); text-align: center; border: 1px solid var(--border-color);">
              <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Total Rows</div>
              <div style="font-size: 1.25rem; font-weight: 700; color: var(--text-primary);">${totalCount}</div>
            </div>
            <div style="background: rgba(16, 185, 129, 0.08); padding: 12px; border-radius: var(--radius-sm); text-align: center; border: 1px solid rgba(16, 185, 129, 0.2);">
              <div style="font-size: 0.75rem; color: var(--success); text-transform: uppercase;">Valid Records</div>
              <div style="font-size: 1.25rem; font-weight: 700; color: var(--success);">${validCount}</div>
            </div>
            <div style="background: ${invalidCount > 0 ? 'rgba(239, 68, 68, 0.08)' : 'var(--bg-secondary)'}; padding: 12px; border-radius: var(--radius-sm); text-align: center; border: 1px solid ${invalidCount > 0 ? 'rgba(239, 68, 68, 0.2)' : 'var(--border-color)'};">
              <div style="font-size: 0.75rem; color: ${invalidCount > 0 ? 'var(--danger)' : 'var(--text-muted)'}; text-transform: uppercase;">Invalid Rows</div>
              <div style="font-size: 1.25rem; font-weight: 700; color: ${invalidCount > 0 ? 'var(--danger)' : 'var(--text-muted)'};">${invalidCount}</div>
            </div>
          </div>
        `;

        if (invalidCount > 0 && previewData.errors && previewData.errors.length > 0) {
          previewHtml += `
            <div style="margin-bottom: 14px; max-height: 120px; overflow-y: auto; background: #fff5f5; border: 1px solid #feb2b2; border-radius: var(--radius-sm); padding: 10px 14px; font-size: 0.8rem;">
              <div style="font-weight: 600; color: #c53030; margin-bottom: 4px;">⚠️ Rows with Issues:</div>
              ${previewData.errors.slice(0, 10).map(e => `
                <div style="color: #742a2a; margin-bottom: 3px;">
                  • <strong>Row ${e.row}:</strong> ${UI.escapeHtml((e.issues || []).join(', '))}
                </div>
              `).join('')}
              ${previewData.errors.length > 10 ? `<div style="font-style: italic; color: #9b2c2c;">... and ${previewData.errors.length - 10} more rows</div>` : ''}
            </div>
          `;
        }

        if (validCount > 0) {
          confirmBtn.textContent = `Confirm & Import ${validCount} Valid Records`;
          confirmBtn.style.display = 'inline-block';
        }

        previewArea.innerHTML = previewHtml;
        previewArea.style.display = 'block';

      } catch (err) {
        loadingEl.style.display = 'none';
        UI.showToast('Failed to process file: ' + err.message, 'danger');
      }
    });

    confirmBtn.onclick = async () => {
      if (!previewData) return;
      const rowsToImport = previewData.valid_rows || previewData.preview_rows.filter(r => r.is_valid).map(r => r.data);
      if (!rowsToImport || rowsToImport.length === 0) {
        UI.showToast('No valid rows found to import', 'warning');
        return;
      }

      UI.setButtonLoading(confirmBtn, true, 'Importing...');
      try {
        const res = await ApiClient.post('/api/import/confirm', {
          module: moduleName,
          rows: rowsToImport,
          filename: previewData.filename
        });

        UI.setButtonLoading(confirmBtn, false);

        if (!res.success) {
          UI.showToast(res.error || res.message || 'Import failed', 'danger');
          return;
        }

        UI.showToast(`✅ Successfully imported ${res.data?.imported_count || rowsToImport.length} ${moduleName}!`, 'success');
        closeModal();
        if (typeof onComplete === 'function') {
          onComplete();
        }
      } catch (err) {
        UI.setButtonLoading(confirmBtn, false);
        UI.showToast('Failed to complete import: ' + err.message, 'danger');
      }
    };

    modal.classList.add('active');
  },

  async bulkDelete(moduleName, selectedIds, onComplete) {
    if (!selectedIds || selectedIds.length === 0) {
      UI.showToast('No records selected', 'warning');
      return;
    }
    const confirmed = await UI.confirm({
      title: 'Bulk Delete',
      message: `Are you sure you want to permanently delete ${selectedIds.length} selected record(s)? This action cannot be undone.`,
      confirmText: 'Yes, Delete',
      isDanger: true
    });
    if (!confirmed) return;

    try {
      const res = await ApiClient.post(`/api/${moduleName}/bulk-action`, {
        action: 'delete',
        ids: selectedIds
      });
      if (res.success) {
        UI.showToast(`Successfully deleted ${res.data?.affected || selectedIds.length} record(s)`, 'success');
        if (typeof onComplete === 'function') onComplete();
      } else {
        UI.showToast(res.error || res.message || 'Bulk delete failed', 'danger');
      }
    } catch (err) {
      UI.showToast('Bulk delete failed: ' + err.message, 'danger');
    }
  },

  async bulkStatus(moduleName, selectedIds, statuses, onComplete) {
    if (!selectedIds || selectedIds.length === 0) {
      UI.showToast('No records selected', 'warning');
      return;
    }
    const statusOptions = statuses.map(s => `<option value="${s.value}">${s.label}</option>`).join('');
    let modal = document.getElementById('bulkStatusModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'bulkStatusModal';
      modal.className = 'modal';
      document.body.appendChild(modal);
    }
    modal.innerHTML = `
      <div class="modal-backdrop"></div>
      <div class="modal-dialog" style="max-width: 420px; text-align: left;">
        <div class="modal-header">
          <h3 class="modal-title">Update Status (${selectedIds.length} items)</h3>
          <button type="button" class="modal-close" id="bulkStatusCloseX">&times;</button>
        </div>
        <div class="modal-body" style="padding: 20px;">
          <label class="form-label" style="font-weight: 600;">Select New Status</label>
          <select id="bulkStatusSelect" class="form-select">
            ${statusOptions}
          </select>
        </div>
        <div class="modal-footer" style="display:flex; justify-content: flex-end; gap: 10px; padding: 14px 20px; border-top: 1px solid var(--border-color);">
          <button type="button" class="btn btn-outline btn-sm" id="bulkStatusCancelBtn">Cancel</button>
          <button type="button" class="btn btn-primary btn-sm" id="bulkStatusSubmitBtn">Update Status</button>
        </div>
      </div>
    `;

    function close() { modal.classList.remove('active'); }
    modal.querySelector('#bulkStatusCloseX').onclick = close;
    modal.querySelector('#bulkStatusCancelBtn').onclick = close;
    modal.querySelector('.modal-backdrop').onclick = close;

    modal.querySelector('#bulkStatusSubmitBtn').onclick = async () => {
      const val = modal.querySelector('#bulkStatusSelect').value;
      try {
        const res = await ApiClient.post(`/api/${moduleName}/bulk-action`, {
          action: 'status',
          ids: selectedIds,
          value: val
        });
        if (res.success) {
          UI.showToast(`Updated status for ${res.data?.affected || selectedIds.length} item(s)`, 'success');
          close();
          if (typeof onComplete === 'function') onComplete();
        } else {
          UI.showToast(res.error || res.message || 'Status update failed', 'danger');
        }
      } catch (e) {
        UI.showToast('Status update failed: ' + e.message, 'danger');
      }
    };
    modal.classList.add('active');
  },

  async bulkAssign(moduleName, selectedIds, onComplete) {
    if (!selectedIds || selectedIds.length === 0) {
      UI.showToast('No records selected', 'warning');
      return;
    }
    let modal = document.getElementById('bulkAssignModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'bulkAssignModal';
      modal.className = 'modal';
      document.body.appendChild(modal);
    }
    modal.innerHTML = `
      <div class="modal-backdrop"></div>
      <div class="modal-dialog" style="max-width: 420px; text-align: left;">
        <div class="modal-header">
          <h3 class="modal-title">Assign Representative (${selectedIds.length} items)</h3>
          <button type="button" class="modal-close" id="bulkAssignCloseX">&times;</button>
        </div>
        <div class="modal-body" style="padding: 20px;">
          <label class="form-label" style="font-weight: 600;">Select Assignee</label>
          <select id="bulkAssignSelect" class="form-select">
            <option value="">Loading representatives...</option>
          </select>
        </div>
        <div class="modal-footer" style="display:flex; justify-content: flex-end; gap: 10px; padding: 14px 20px; border-top: 1px solid var(--border-color);">
          <button type="button" class="btn btn-outline btn-sm" id="bulkAssignCancelBtn">Cancel</button>
          <button type="button" class="btn btn-primary btn-sm" id="bulkAssignSubmitBtn">Assign</button>
        </div>
      </div>
    `;

    function close() { modal.classList.remove('active'); }
    modal.querySelector('#bulkAssignCloseX').onclick = close;
    modal.querySelector('#bulkAssignCancelBtn').onclick = close;
    modal.querySelector('.modal-backdrop').onclick = close;

    await UI.loadAssignees('bulkAssignSelect');

    modal.querySelector('#bulkAssignSubmitBtn').onclick = async () => {
      const val = modal.querySelector('#bulkAssignSelect').value;
      if (!val) {
        UI.showToast('Please select a representative', 'warning');
        return;
      }
      try {
        const res = await ApiClient.post(`/api/${moduleName}/bulk-action`, {
          action: 'assign',
          ids: selectedIds,
          value: parseInt(val, 10)
        });
        if (res.success) {
          UI.showToast(`Assigned ${res.data?.affected || selectedIds.length} item(s)`, 'success');
          close();
          if (typeof onComplete === 'function') onComplete();
        } else {
          UI.showToast(res.error || res.message || 'Bulk assign failed', 'danger');
        }
      } catch (e) {
        UI.showToast('Bulk assign failed: ' + e.message, 'danger');
      }
    };
    modal.classList.add('active');
  }
};


if (typeof window !== 'undefined') {
  window.UI = UI;
}
