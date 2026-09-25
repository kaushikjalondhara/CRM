/**
 * CRM Calendar System
 * Interactive month view with aggregated Meetings, Calls, Tasks, and Events.
 */

let calDate = new Date();

document.addEventListener('DOMContentLoaded', () => {
  initCalendar();
});

function initCalendar() {
  document.getElementById('calPrevBtn')?.addEventListener('click', () => {
    calDate.setMonth(calDate.getMonth() - 1);
    renderCalendar();
  });

  document.getElementById('calNextBtn')?.addEventListener('click', () => {
    calDate.setMonth(calDate.getMonth() + 1);
    renderCalendar();
  });

  document.getElementById('calTodayBtn')?.addEventListener('click', () => {
    calDate = new Date();
    renderCalendar();
  });

  document.getElementById('btnNewEvent')?.addEventListener('click', () => {
    const now = new Date();
    const startIso = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    const endIso = new Date(now.getTime() - now.getTimezoneOffset() * 60000 + 3600000).toISOString().slice(0, 16);
    
    document.getElementById('eventTitle').value = '';
    document.getElementById('eventType').value = 'event';
    document.getElementById('eventLocation').value = '';
    document.getElementById('eventStart').value = startIso;
    document.getElementById('eventEnd').value = endIso;
    document.getElementById('eventDesc').value = '';

    UI.openModal('eventModal');
  });

  document.getElementById('eventForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const saveBtn = document.getElementById('saveEventBtn');
    UI.setButtonLoading(saveBtn, true, 'Saving...');

    const payload = {
      title: document.getElementById('eventTitle').value.trim(),
      event_type: document.getElementById('eventType').value,
      location: document.getElementById('eventLocation').value.trim() || null,
      start_time: document.getElementById('eventStart').value,
      end_time: document.getElementById('eventEnd').value,
      description: document.getElementById('eventDesc').value.trim() || null
    };

    try {
      const res = await ApiClient.post('/api/calendar/events', payload);
      if (res.success) {
        UI.showToast('Event created successfully!', 'success');
        UI.closeModal('eventModal');
        renderCalendar();
      } else {
        UI.showToast(res.message || 'Failed to create event', 'danger');
      }
    } catch (err) {
      UI.showToast('Error saving event', 'danger');
    } finally {
      UI.setButtonLoading(saveBtn, false);
    }
  });

  renderCalendar();
}

async function renderCalendar() {
  const grid = document.getElementById('calendarGrid');
  const monthTitle = document.getElementById('calendarCurrentMonth');
  if (!grid) return;

  const year = calDate.getFullYear();
  const month = calDate.getMonth(); // 0-indexed

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];
  if (monthTitle) {
    monthTitle.textContent = `${monthNames[month]} ${year}`;
  }

  // Remove existing day cells (preserve the 7 header cells)
  const existingCells = grid.querySelectorAll('.calendar-cell');
  existingCells.forEach(c => c.remove());

  // Calculate start of grid (Sunday)
  const firstDayOfMonth = new Date(year, month, 1);
  const startDayIndex = firstDayOfMonth.getDay(); // 0 is Sunday
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrevMonth = new Date(year, month, 0).getDate();

  const totalGridSlots = 35 < (startDayIndex + daysInMonth) ? 42 : 35;

  // Calculate visible date range for backend query
  const gridStartDate = new Date(year, month, 1 - startDayIndex);
  const gridEndDate = new Date(year, month, totalGridSlots - startDayIndex);

  const startStr = gridStartDate.toISOString().slice(0, 10);
  const endStr = gridEndDate.toISOString().slice(0, 10);

  // Fetch events for this window
  let events = [];
  try {
    const res = await ApiClient.get(`/api/calendar/events?start_date=${startStr}&end_date=${endStr}`);
    if (res.success && res.data) {
      events = res.data.events || [];
    }
  } catch (err) {
    console.error('Failed to fetch calendar events:', err);
  }

  // Group events by YYYY-MM-DD
  const eventsByDate = {};
  events.forEach(ev => {
    const dateKey = (ev.start_time || '').slice(0, 10);
    if (!eventsByDate[dateKey]) eventsByDate[dateKey] = [];
    eventsByDate[dateKey].push(ev);
  });

  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

  for (let i = 0; i < totalGridSlots; i++) {
    const dayNumber = i - startDayIndex + 1;
    const cellDate = new Date(year, month, dayNumber);
    const dateKey = `${cellDate.getFullYear()}-${String(cellDate.getMonth() + 1).padStart(2, '0')}-${String(cellDate.getDate()).padStart(2, '0')}`;

    const cell = document.createElement('div');
    cell.className = 'calendar-cell';

    const isCurrentMonth = cellDate.getMonth() === month;
    if (!isCurrentMonth) cell.classList.add('other-month');
    if (dateKey === todayStr) cell.classList.add('today');

    cell.innerHTML = `<div class="cal-date-number">${cellDate.getDate()}</div>`;

    const dayEvents = eventsByDate[dateKey] || [];
    dayEvents.forEach(ev => {
      const pill = document.createElement('div');
      pill.className = `cal-event-pill cal-pill-${ev.event_type || 'event'}`;
      pill.textContent = ev.title;
      pill.title = `${ev.title} (${ev.event_type})`;
      pill.onclick = (e) => {
        e.stopPropagation();
        showEventDetails(ev);
      };
      cell.appendChild(pill);
    });

    grid.appendChild(cell);
  }
}

function showEventDetails(ev) {
  const modal = document.getElementById('eventDetailsModal');
  const body = document.getElementById('detailModalBody');
  const title = document.getElementById('detailModalTitle');
  if (!modal || !body) return;

  title.textContent = ev.title;

  const typeBadges = {
    meeting: '<span class="badge badge-primary">Meeting</span>',
    call: '<span class="badge badge-warning">Call</span>',
    task: '<span class="badge badge-secondary">Task</span>',
    event: '<span class="badge badge-success">Event</span>'
  };

  body.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
      ${typeBadges[ev.event_type] || `<span class="badge">${UI.escapeHtml(ev.event_type)}</span>`}
      <span style="font-size: 0.8rem; color: var(--text-muted);">${ev.status ? UI.escapeHtml(ev.status.toUpperCase()) : ''}</span>
    </div>
    <div class="info-item" style="margin-bottom: 10px;">
      <span class="info-label">Start Time</span>
      <span class="info-value">${UI.formatDateTime(ev.start_time)}</span>
    </div>
    <div class="info-item" style="margin-bottom: 10px;">
      <span class="info-label">End Time</span>
      <span class="info-value">${UI.formatDateTime(ev.end_time)}</span>
    </div>
    ${ev.location ? `
      <div class="info-item" style="margin-bottom: 10px;">
        <span class="info-label">Location / Link</span>
        <span class="info-value">${UI.escapeHtml(ev.location)}</span>
      </div>
    ` : ''}
    ${ev.customer_name ? `
      <div class="info-item" style="margin-bottom: 10px;">
        <span class="info-label">Customer</span>
        <span class="info-value"><a href="customer-details.html?id=${ev.customer_id}">${UI.escapeHtml(ev.customer_name)}</a></span>
      </div>
    ` : ''}
    ${ev.description ? `
      <div class="info-item" style="margin-top: 14px;">
        <span class="info-label">Description / Agenda</span>
        <p style="margin: 4px 0 0 0; font-size: 0.85rem; color: var(--text-secondary); line-height: 1.4;">${UI.escapeHtml(ev.description)}</p>
      </div>
    ` : ''}
  `;

  UI.openModal('eventDetailsModal');
}
