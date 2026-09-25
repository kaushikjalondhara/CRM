/**
 * CRM Email Module
 * Handles email logs, template management, and compose workflows.
 */

let currentPage = 1;
let currentTotalPages = 1;
let cachedTemplates = [];
let cachedCustomers = [];

document.addEventListener('DOMContentLoaded', async () => {
  const user = await Auth.requireAuth();
  if (!user) return;

  UI.updateNotificationBadge();
  setupEventListeners();
  checkSmtpStatus();
  loadCustomers();
  loadTemplates();
  loadEmails();
});

function setupEventListeners() {
  document.getElementById('composeEmailBtn')?.addEventListener('click', openComposeModal);
  document.getElementById('createTemplateBtn')?.addEventListener('click', openCreateTemplateModal);

  document.getElementById('searchInput')?.addEventListener('input', debounce(() => {
    currentPage = 1;
    loadEmails();
  }, 350));

  document.getElementById('statusFilter')?.addEventListener('change', () => {
    currentPage = 1;
    loadEmails();
  });

  document.getElementById('clearFiltersBtn')?.addEventListener('click', () => {
    document.getElementById('searchInput').value = '';
    document.getElementById('statusFilter').value = '';
    currentPage = 1;
    loadEmails();
  });

  document.getElementById('prevPageBtn')?.addEventListener('click', () => {
    if (currentPage > 1) {
      currentPage--;
      loadEmails();
    }
  });

  document.getElementById('nextPageBtn')?.addEventListener('click', () => {
    if (currentPage < currentTotalPages) {
      currentPage++;
      loadEmails();
    }
  });

  document.getElementById('composeForm')?.addEventListener('submit', handleComposeSubmit);
  document.getElementById('templateForm')?.addEventListener('submit', handleTemplateSubmit);

  document.getElementById('composeCustomer')?.addEventListener('change', (e) => {
    const custId = e.target.value;
    if (!custId) return;
    const c = cachedCustomers.find(item => String(item.id) === String(custId));
    if (c && c.email) {
      document.getElementById('composeRecipient').value = c.email;
    }
  });

  document.getElementById('composeTemplateSelect')?.addEventListener('change', (e) => {
    const tmplId = e.target.value;
    if (!tmplId) return;
    const t = cachedTemplates.find(item => String(item.id) === String(tmplId));
    if (t) {
      document.getElementById('composeSubject').value = t.subject;
      document.getElementById('composeMessage').value = t.body;
    }
  });
}

function switchTab(tabId, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(tabId)?.classList.add('active');
}

async function checkSmtpStatus() {
  try {
    const res = await ApiClient.get('/api/emails/smtp-status');
    const banner = document.getElementById('smtpNoticeBanner');
    if (!banner) return;

    if (res.success && res.data) {
      if (!res.data.is_smtp_configured) {
        banner.style.display = 'block';
        banner.style.background = '#feebc8';
        banner.style.color = '#7b341e';
        banner.style.border = '1px solid #fbd38d';
        banner.innerHTML = `
          <strong>⚙️ Safe Development Mode:</strong> Email sending is not configured (SMTP credentials not found in <code>.env</code>). Composed messages are safely saved to the database as <strong>drafts</strong> without faking delivery.
        `;
      } else {
        banner.style.display = 'block';
        banner.style.background = '#c6f6d5';
        banner.style.color = '#22543d';
        banner.style.border = '1px solid #9ae6b4';
        banner.innerHTML = `<strong>✓ SMTP Online:</strong> Real email delivery is enabled and configured.`;
      }
    }
  } catch (e) {
    console.warn('Could not check SMTP status', e);
  }
}

async function loadCustomers() {
  try {
    const res = await ApiClient.get('/api/customers?per_page=100');
    if (res.success && res.data?.customers) {
      cachedCustomers = res.data.customers;
      const sel = document.getElementById('composeCustomer');
      if (sel) {
        sel.innerHTML = '<option value="">-- None --</option>' +
          cachedCustomers.map(c => `<option value="${c.id}">${UI.escapeHtml(c.first_name)} ${UI.escapeHtml(c.last_name)} (${UI.escapeHtml(c.email || 'No email')})</option>`).join('');
      }
    }
  } catch (e) {}
}

async function loadTemplates() {
  const tbody = document.getElementById('templatesTableBody');
  const composeTmplSelect = document.getElementById('composeTemplateSelect');
  if (!tbody) return;

  try {
    const res = await ApiClient.get('/api/emails/templates');
    if (!res.success) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #e53e3e;">Failed to load templates</td></tr>';
      return;
    }

    cachedTemplates = res.data.templates || [];

    if (composeTmplSelect) {
      composeTmplSelect.innerHTML = '<option value="">-- Select Template --</option>' +
        cachedTemplates.map(t => `<option value="${t.id}">${UI.escapeHtml(t.name)}</option>`).join('');
    }

    if (cachedTemplates.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 32px; color: #718096;">No email templates found. Click "+ New Template" to create one.</td></tr>';
      return;
    }

    tbody.innerHTML = cachedTemplates.map(t => `
      <tr>
        <td style="font-weight: 600; color: #073472;">${UI.escapeHtml(t.name)}</td>
        <td>${UI.escapeHtml(t.subject)}</td>
        <td style="font-size: 0.85rem; color: #718096; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${UI.escapeHtml(t.body)}</td>
        <td style="font-size: 0.85rem;">${UI.escapeHtml(t.creator_name || 'System')}</td>
        <td style="text-align: right; white-space: nowrap;">
          <button class="btn btn-secondary btn-sm" onclick="useTemplateInCompose(${t.id})">Use</button>
          <button class="btn btn-secondary btn-sm" style="margin-left: 4px;" onclick="openEditTemplateModal(${t.id})">Edit</button>
          <button class="btn btn-danger btn-sm" style="margin-left: 4px;" onclick="deleteTemplate(${t.id}, '${UI.escapeHtml(t.name)}')">Delete</button>
        </td>
      </tr>
    `).join('');

  } catch (err) {
    console.error('Failed to load templates', err);
  }
}

async function loadEmails() {
  const tbody = document.getElementById('emailsTableBody');
  if (!tbody) return;

  const search = document.getElementById('searchInput')?.value.trim() || '';
  const status = document.getElementById('statusFilter')?.value || '';

  const params = new URLSearchParams({
    page: currentPage,
    per_page: 15
  });
  if (search) params.append('search', search);
  if (status) params.append('status', status);

  try {
    const res = await ApiClient.get(`/api/emails?${params.toString()}`);
    if (!res.success) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #e53e3e; padding: 24px;">Failed to load emails: ${UI.escapeHtml(res.data?.message || 'Server error')}</td></tr>`;
      return;
    }

    const { emails, total, page, total_pages } = res.data.data;
    currentPage = page;
    currentTotalPages = total_pages || 1;

    document.getElementById('paginationInfo').textContent = `Showing ${emails.length} of ${total} emails (Page ${page} of ${currentTotalPages})`;
    document.getElementById('prevPageBtn').disabled = currentPage <= 1;
    document.getElementById('nextPageBtn').disabled = currentPage >= currentTotalPages;

    if (emails.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; padding: 48px 16px;">
            <div style="font-size: 2.5rem; margin-bottom: 8px;">✉️</div>
            <div style="font-weight: 600; font-size: 1.1rem; color: #2d3748;">No Email Records Found</div>
            <p style="color: #718096; margin-top: 4px;">Click "✉️ Compose Email" to log or send a message.</p>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = emails.map(e => {
      let badge = '';
      if (e.status === 'sent') {
        badge = '<span class="status-badge" style="background: #e6fffa; color: #234e52; border: 1px solid #b2f5ea;">Sent</span>';
      } else if (e.status === 'failed') {
        badge = '<span class="status-badge" style="background: #fff5f5; color: #c53030; border: 1px solid #fed7d7;">Failed</span>';
      } else {
        badge = '<span class="status-badge" style="background: #feebc8; color: #7b341e; border: 1px solid #fbd38d;">Draft</span>';
      }

      let linkedRecord = '—';
      if (e.customer_name) linkedRecord = `👤 ${UI.escapeHtml(e.customer_name)}`;
      else if (e.lead_name) linkedRecord = `🎯 ${UI.escapeHtml(e.lead_name)}`;
      else if (e.deal_title) linkedRecord = `💼 ${UI.escapeHtml(e.deal_title)}`;

      return `
        <tr>
          <td>${UI.formatDateTime(e.sent_at || e.created_at)}</td>
          <td style="font-weight: 600; color: #2d3748;">${UI.escapeHtml(e.recipient_email)}</td>
          <td style="font-weight: 600;">${UI.escapeHtml(e.subject)}</td>
          <td style="font-size: 0.85rem; color: #4a5568;">${linkedRecord}</td>
          <td style="font-size: 0.85rem; color: #718096;">${UI.escapeHtml(e.sender_name || 'System')}</td>
          <td>${badge}</td>
          <td style="text-align: right; white-space: nowrap;">
            <button class="btn btn-secondary btn-sm" onclick="viewEmail(${e.id})">View</button>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load emails', err);
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #e53e3e; padding: 24px;">An unexpected error occurred.</td></tr>`;
  }
}

function openComposeModal() {
  document.getElementById('composeForm').reset();
  UI.openModal('composeModal');
}

function useTemplateInCompose(templateId) {
  const t = cachedTemplates.find(item => item.id === templateId);
  if (!t) return;

  document.getElementById('composeForm').reset();
  document.getElementById('composeTemplateSelect').value = templateId;
  document.getElementById('composeSubject').value = t.subject;
  document.getElementById('composeMessage').value = t.body;

  UI.openModal('composeModal');
}

async function handleComposeSubmit(e) {
  e.preventDefault();
  const customerId = document.getElementById('composeCustomer').value;
  const payload = {
    recipient_email: document.getElementById('composeRecipient').value.trim(),
    subject: document.getElementById('composeSubject').value.trim(),
    message: document.getElementById('composeMessage').value.trim(),
    customer_id: customerId ? parseInt(customerId) : undefined
  };

  const btn = document.getElementById('sendEmailBtn');
  UI.setButtonLoading(btn, true, 'Sending...');

  try {
    const res = await ApiClient.post('/api/emails', payload);
    if (res.success) {
      UI.showToast(res.data?.message || 'Email processed successfully', 'success');
      UI.closeModal('composeModal');
      loadEmails();
    } else {
      UI.showToast(res.data?.message || 'Failed to send email', 'danger');
    }
  } catch (err) {
    UI.showToast('Error processing email', 'danger');
  } finally {
    UI.setButtonLoading(btn, false);
  }
}

function openCreateTemplateModal() {
  document.getElementById('templateForm').reset();
  document.getElementById('templateId').value = '';
  document.getElementById('templateModalTitle').textContent = 'Create Email Template';
  UI.openModal('templateModal');
}

async function openEditTemplateModal(templateId) {
  try {
    const res = await ApiClient.get(`/api/emails/templates/${templateId}`);
    if (!res.success) {
      UI.showToast('Template not found', 'danger');
      return;
    }
    const t = res.data.template;
    document.getElementById('templateId').value = t.id;
    document.getElementById('tmplName').value = t.name;
    document.getElementById('tmplSubject').value = t.subject;
    document.getElementById('tmplBody').value = t.body;
    document.getElementById('templateModalTitle').textContent = `Edit Template: ${t.name}`;
    UI.openModal('templateModal');
  } catch (err) {
    UI.showToast('Error fetching template details', 'danger');
  }
}

async function handleTemplateSubmit(e) {
  e.preventDefault();
  const templateId = document.getElementById('templateId').value;
  const payload = {
    name: document.getElementById('tmplName').value.trim(),
    subject: document.getElementById('tmplSubject').value.trim(),
    body: document.getElementById('tmplBody').value.trim()
  };

  const btn = document.getElementById('saveTemplateBtn');
  UI.setButtonLoading(btn, true, 'Saving...');

  try {
    let res;
    if (templateId) {
      res = await ApiClient.put(`/api/emails/templates/${templateId}`, payload);
    } else {
      res = await ApiClient.post('/api/emails/templates', payload);
    }

    if (res.success) {
      UI.showToast(templateId ? 'Template updated' : 'Template created', 'success');
      UI.closeModal('templateModal');
      loadTemplates();
    } else {
      UI.showToast(res.data?.message || 'Failed to save template', 'danger');
    }
  } catch (err) {
    UI.showToast('Error saving template', 'danger');
  } finally {
    UI.setButtonLoading(btn, false);
  }
}

async function deleteTemplate(templateId, name) {
  const confirmed = await UI.confirm({
    title: 'Delete Template',
    message: `Are you sure you want to delete template '${name}'?`,
    confirmText: 'Delete',
    cancelText: 'Cancel',
    isDanger: true
  });
  if (!confirmed) return;

  try {
    const res = await ApiClient.delete(`/api/emails/templates/${templateId}`);
    if (res.success) {
      UI.showToast('Template deleted successfully', 'success');
      loadTemplates();
    } else {
      UI.showToast(res.data?.message || 'Failed to delete template', 'danger');
    }
  } catch (err) {
    UI.showToast('Error deleting template', 'danger');
  }
}

async function viewEmail(emailId) {
  try {
    const res = await ApiClient.get(`/api/emails/${emailId}`);
    if (!res.success) {
      UI.showToast('Email not found', 'danger');
      return;
    }
    const e = res.data.email;

    document.getElementById('viewEmailSubject').textContent = e.subject;
    const bodyEl = document.getElementById('viewEmailBodyContent');
    bodyEl.innerHTML = `
      <div style="font-size: 0.85rem; color: #718096; margin-bottom: 16px; border-bottom: 1px solid #edf2f7; padding-bottom: 12px;">
        <div><strong>To:</strong> ${UI.escapeHtml(e.recipient_email)}</div>
        <div style="margin-top: 2px;"><strong>From:</strong> ${UI.escapeHtml(e.sender_name || 'System')}</div>
        <div style="margin-top: 2px;"><strong>Date:</strong> ${UI.formatDateTime(e.sent_at || e.created_at)}</div>
        <div style="margin-top: 2px;"><strong>Status:</strong> ${UI.escapeHtml(e.status.toUpperCase())}</div>
      </div>
      <div style="line-height: 1.6; color: #2d3748; white-space: pre-wrap; font-family: inherit;">${UI.escapeHtml(e.message)}</div>
    `;
    UI.openModal('viewEmailModal');
  } catch (err) {
    UI.showToast('Error opening email view', 'danger');
  }
}

function debounce(fn, delay) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}
