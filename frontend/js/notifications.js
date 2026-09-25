/**
 * CRM Notifications Module
 * Manages in-app alerts, unread counts, and notification lifecycle.
 */

let currentPage = 1;
let currentTotalPages = 1;

document.addEventListener('DOMContentLoaded', async () => {
  const user = await Auth.requireAuth();
  if (!user) return;

  setupEventListeners();
  loadNotifications();
});

function setupEventListeners() {
  document.getElementById('markAllReadBtn')?.addEventListener('click', handleMarkAllRead);

  document.getElementById('typeFilter')?.addEventListener('change', () => {
    currentPage = 1;
    loadNotifications();
  });

  document.getElementById('readFilter')?.addEventListener('change', () => {
    currentPage = 1;
    loadNotifications();
  });

  document.getElementById('prevPageBtn')?.addEventListener('click', () => {
    if (currentPage > 1) {
      currentPage--;
      loadNotifications();
    }
  });

  document.getElementById('nextPageBtn')?.addEventListener('click', () => {
    if (currentPage < currentTotalPages) {
      currentPage++;
      loadNotifications();
    }
  });
}

async function loadNotifications() {
  const container = document.getElementById('notificationsContainer');
  if (!container) return;

  const notifType = document.getElementById('typeFilter')?.value || '';
  const isRead = document.getElementById('readFilter')?.value || '';

  const params = new URLSearchParams({
    page: currentPage,
    per_page: 20
  });
  if (notifType) params.append('type', notifType);
  if (isRead !== '') params.append('is_read', isRead);

  try {
    const res = await ApiClient.get(`/api/notifications?${params.toString()}`);
    if (!res.success) {
      container.innerHTML = `<div style="text-align: center; color: #e53e3e; padding: 32px;">Failed to load alerts: ${UI.escapeHtml(res.data?.message || 'Server error')}</div>`;
      return;
    }

    const { notifications, unread_count, total, page, total_pages } = res.data.data;
    currentPage = page;
    currentTotalPages = total_pages || 1;

    document.getElementById('unreadBadgeText').textContent = unread_count;
    UI.updateNotificationBadge();

    document.getElementById('paginationInfo').textContent = `Showing ${notifications.length} of ${total} alerts (Page ${page} of ${currentTotalPages})`;
    document.getElementById('prevPageBtn').disabled = currentPage <= 1;
    document.getElementById('nextPageBtn').disabled = currentPage >= currentTotalPages;

    if (notifications.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 64px 16px; background: #fff; border-radius: 8px; border: 1px solid #e2e8f0;">
          <div style="font-size: 2.5rem; margin-bottom: 8px;">🔔</div>
          <div style="font-weight: 600; font-size: 1.1rem; color: #2d3748;">All Caught Up!</div>
          <p style="color: #718096; margin-top: 4px;">You have no notifications matching your current filters.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = notifications.map(n => {
      let icon = '🔔';
      let iconBg = '#edf2f7';
      let iconColor = '#4a5568';

      if (n.type === 'payment') {
        icon = '💳';
        iconBg = '#e6fffa';
        iconColor = '#234e52';
      } else if (n.type === 'invoice') {
        icon = '🧾';
        iconBg = '#ebf8ff';
        iconColor = '#2b6cb0';
      } else if (n.type === 'task') {
        icon = '✅';
        iconBg = '#f0fff4';
        iconColor = '#22543d';
      } else if (n.type === 'meeting') {
        icon = '📅';
        iconBg = '#faf5ff';
        iconColor = '#553c9a';
      } else if (n.type === 'call') {
        icon = '📞';
        iconBg = '#feebc8';
        iconColor = '#7b341e';
      } else if (n.type === 'lead') {
        icon = '🎯';
        iconBg = '#fffff0';
        iconColor = '#744210';
      } else if (n.type === 'deal') {
        icon = '💼';
        iconBg = '#ebf8ff';
        iconColor = '#2a4365';
      }

      let navAction = '';
      if (n.related_type && n.related_id) {
        let targetHref = '#';
        if (n.related_type === 'invoice') targetHref = `invoices.html`;
        else if (n.related_type === 'customer') targetHref = `customer-details.html?id=${n.related_id}`;
        else if (n.related_type === 'lead') targetHref = `lead-details.html?id=${n.related_id}`;
        else if (n.related_type === 'task') targetHref = `tasks.html`;
        else if (n.related_type === 'meeting') targetHref = `meetings.html`;
        else if (n.related_type === 'call') targetHref = `calls.html`;

        navAction = `<a href="${targetHref}" class="btn btn-secondary btn-sm" style="padding: 4px 8px; font-size: 0.8rem; margin-right: 6px;">View Details</a>`;
      }

      return `
        <div class="notif-card ${!n.is_read ? 'unread' : ''}" id="notif_${n.id}">
          <div class="notif-icon-box" style="background: ${iconBg}; color: ${iconColor};">
            ${icon}
          </div>
          <div class="notif-body">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
              <div class="notif-title">${UI.escapeHtml(n.title)}</div>
              <div style="display: flex; gap: 4px; align-items: center;">
                ${navAction}
                ${!n.is_read ? `
                  <button class="btn btn-secondary btn-sm" style="padding: 4px 8px; font-size: 0.8rem;" onclick="markRead(${n.id})">Mark Read</button>
                ` : ''}
                <button class="btn btn-danger btn-sm" style="padding: 4px 8px; font-size: 0.8rem;" onclick="removeNotif(${n.id})">✕</button>
              </div>
            </div>
            <div class="notif-msg">${UI.escapeHtml(n.message)}</div>
            <div class="notif-time">${UI.formatDateTime(n.created_at)}</div>
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load notifications', err);
  }
}

async function markRead(notificationId) {
  try {
    const res = await ApiClient.put(`/api/notifications/${notificationId}/read`);
    if (res.success) {
      const card = document.getElementById(`notif_${notificationId}`);
      if (card) {
        card.classList.remove('unread');
        // Remove mark read button
        const btn = card.querySelector("button[onclick*='markRead']");
        if (btn) btn.remove();
      }
      UI.updateNotificationBadge();
      loadNotifications();
    }
  } catch (e) {
    UI.showToast('Failed to mark notification as read', 'danger');
  }
}

async function handleMarkAllRead() {
  try {
    const res = await ApiClient.put('/api/notifications/read-all');
    if (res.success) {
      UI.showToast('All notifications marked as read', 'success');
      loadNotifications();
    }
  } catch (e) {
    UI.showToast('Failed to mark all as read', 'danger');
  }
}

async function removeNotif(notificationId) {
  try {
    const res = await ApiClient.delete(`/api/notifications/${notificationId}`);
    if (res.success) {
      const card = document.getElementById(`notif_${notificationId}`);
      if (card) card.remove();
      loadNotifications();
    }
  } catch (e) {
    UI.showToast('Failed to delete notification', 'danger');
  }
}
