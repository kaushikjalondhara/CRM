/**
 * CRM Tasks Management Module
 * Handles task listing, priority/status filtering, quick status toggling, and CRUD operations.
 */

let currentStatusFilter = '';
let currentPriorityFilter = '';
let bulkSelection = null;

document.addEventListener('DOMContentLoaded', async () => {
  if (typeof Auth !== 'undefined') {
    const user = await Auth.requireAuth();
    if (!user) return;
  }

  initTaskEvents();
  loadTasks();
});

function initTaskEvents() {
  // Bulk selection setup
  bulkSelection = UI.initBulkSelection({
    selectAllId: 'selectAll',
    rowSelector: '.task-row-cb',
    toolbarId: 'bulkActionsToolbar',
    countId: 'bulkSelectedCount'
  });

  // Bulk Actions
  document.getElementById('bulkDeleteBtn')?.addEventListener('click', () => {
    const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
    UI.bulkDelete('tasks', ids, () => {
      if (bulkSelection) bulkSelection.clearSelection();
      loadTasks();
    });
  });

  document.getElementById('bulkStatusBtn')?.addEventListener('click', () => {
    const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
    UI.bulkStatus('tasks', ids, [
      { value: 'pending', label: 'Pending' },
      { value: 'in_progress', label: 'In Progress' },
      { value: 'completed', label: 'Completed' },
      { value: 'cancelled', label: 'Cancelled' }
    ], () => {
      if (bulkSelection) bulkSelection.clearSelection();
      loadTasks();
    });
  });

  document.getElementById('bulkAssignBtn')?.addEventListener('click', () => {
    const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
    UI.bulkAssign('tasks', ids, () => {
      if (bulkSelection) bulkSelection.clearSelection();
      loadTasks();
    });
  });

  const statusFilter = document.getElementById('taskStatusFilter');
  if (statusFilter) {
    statusFilter.addEventListener('change', (e) => {
      currentStatusFilter = e.target.value;
      loadTasks();
    });
  }

  const priorityFilter = document.getElementById('taskPriorityFilter');
  if (priorityFilter) {
    priorityFilter.addEventListener('change', (e) => {
      currentPriorityFilter = e.target.value;
      loadTasks();
    });
  }

  const addBtn = document.getElementById('addTaskBtn');
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      resetTaskForm();
      document.getElementById('taskModalTitle').textContent = 'Create New Task';
      UI.loadAssignees('taskAssignedTo');
      UI.openModal('taskModal');
    });
  }

  const form = document.getElementById('taskForm');
  if (form) {
    form.addEventListener('submit', handleTaskFormSubmit);
  }
}

async function loadTasks() {
  const tbody = document.getElementById('taskTableBody');
  if (!tbody) return;

  if (bulkSelection) bulkSelection.clearSelection();

  tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 24px; color: var(--text-muted);">Loading tasks...</td></tr>';

  const params = new URLSearchParams();
  if (currentStatusFilter) params.append('status', currentStatusFilter);
  if (currentPriorityFilter) params.append('priority', currentPriorityFilter);

  try {
    const res = await ApiClient.get(`/api/tasks?${params.toString()}`);
    if (!res.success || !res.data) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 24px; color: var(--danger);">${UI.escapeHtml(res.error || 'Failed to load tasks')}</td></tr>`;
      return;
    }

    const tasks = res.data.tasks || [];
    if (tasks.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7">
            <div class="empty-state">
              <div class="empty-state-icon">✅</div>
              <div class="empty-state-text">No tasks found</div>
              <div class="empty-state-subtext">Create a task to keep your team organized and on track.</div>
            </div>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = tasks.map(t => {
      let priorityBadge = 'badge-secondary';
      if (t.priority === 'urgent') priorityBadge = 'badge-danger';
      else if (t.priority === 'high') priorityBadge = 'badge-warning';
      else if (t.priority === 'medium') priorityBadge = 'badge-info';

      let statusBadge = 'badge-secondary';
      if (t.status === 'completed') statusBadge = 'badge-success';
      else if (t.status === 'in_progress') statusBadge = 'badge-primary';
      else if (t.status === 'pending') statusBadge = 'badge-warning';

      const isDone = t.status === 'completed';
      const assigned = t.assigned_first_name ? `${UI.escapeHtml(t.assigned_first_name)} ${UI.escapeHtml(t.assigned_last_name || '')}` : 'Unassigned';

      return `
        <tr style="${isDone ? 'opacity: 0.7;' : ''}">
          <td style="width: 40px; text-align: center;">
            <input type="checkbox" class="task-row-cb" value="${t.id}" title="Select Task">
          </td>
          <td>
            <strong style="${isDone ? 'text-decoration: line-through;' : ''}">${UI.escapeHtml(t.title)}</strong>
            ${t.description ? `<div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;">${UI.escapeHtml(t.description)}</div>` : ''}
          </td>
          <td><span class="badge ${priorityBadge}">${UI.escapeHtml(t.priority)}</span></td>
          <td>
            <select class="stage-select" onchange="changeTaskStatus(${t.id}, this.value)">
              <option value="pending" ${t.status === 'pending' ? 'selected' : ''}>Pending</option>
              <option value="in_progress" ${t.status === 'in_progress' ? 'selected' : ''}>In Progress</option>
              <option value="completed" ${t.status === 'completed' ? 'selected' : ''}>Completed</option>
              <option value="cancelled" ${t.status === 'cancelled' ? 'selected' : ''}>Cancelled</option>
            </select>
          </td>
          <td>${UI.formatDate(t.due_date)}</td>
          <td>${assigned}</td>
          <td>
            <div class="table-actions">
              <button class="action-btn" onclick="editTask(${t.id})" title="Edit Task">✏ Edit</button>
              <button class="action-btn btn-danger" onclick="deleteTask(${t.id})" title="Delete Task">🗑</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load tasks:', err);
  }
}

async function toggleTaskStatus(id, checked) {
  const newStatus = checked ? 'completed' : 'pending';
  changeTaskStatus(id, newStatus);
}

async function changeTaskStatus(id, newStatus) {
  try {
    const res = await ApiClient.put(`/api/tasks/${id}/status`, { status: newStatus });
    if (res.success) {
      UI.showToast(`Task marked as ${newStatus}!`, 'success');
      loadTasks();
    } else {
      UI.showToast(res.error || 'Failed to update status', 'danger');
      loadTasks();
    }
  } catch (err) {
    UI.showToast('Error changing task status', 'danger');
    loadTasks();
  }
}

function resetTaskForm() {
  const form = document.getElementById('taskForm');
  if (form) form.reset();
  document.getElementById('taskId').value = '';
}

async function editTask(id) {
  try {
    const res = await ApiClient.get(`/api/tasks/${id}`);
    if (!res.success || !res.data || !res.data.task) {
      UI.showToast(res.error || 'Failed to load task', 'danger');
      return;
    }

    const t = res.data.task;
    document.getElementById('taskId').value = t.id;
    document.getElementById('taskTitle').value = t.title || '';
    document.getElementById('taskDescription').value = t.description || '';
    document.getElementById('taskPriority').value = t.priority || 'medium';
    document.getElementById('taskStatus').value = t.status || 'pending';
    document.getElementById('taskDueDate').value = t.due_date ? t.due_date.split('T')[0] : '';
    document.getElementById('taskRelatedType').value = t.related_to_type || '';
    document.getElementById('taskRelatedId').value = t.related_to_id || '';

    await UI.loadAssignees('taskAssignedTo', t.assigned_to);

    document.getElementById('taskModalTitle').textContent = 'Edit Task';
    UI.openModal('taskModal');
  } catch (err) {
    UI.showToast('Error fetching task details', 'danger');
  }
}

async function handleTaskFormSubmit(e) {
  e.preventDefault();

  const id = document.getElementById('taskId').value;
  const payload = {
    title: document.getElementById('taskTitle').value.trim(),
    description: document.getElementById('taskDescription').value.trim(),
    priority: document.getElementById('taskPriority').value,
    status: document.getElementById('taskStatus').value,
    due_date: document.getElementById('taskDueDate').value || null,
    assigned_to: document.getElementById('taskAssignedTo').value || null,
    related_to_type: document.getElementById('taskRelatedType').value || null,
    related_to_id: parseInt(document.getElementById('taskRelatedId').value) || null,
  };

  if (!payload.title) {
    UI.showToast('Task title is required.', 'warning');
    return;
  }

  const submitBtn = document.querySelector('#taskForm button[type="submit"]');
  UI.setButtonLoading(submitBtn, true, 'Saving...');

  try {
    let res;
    if (id) {
      res = await ApiClient.put(`/api/tasks/${id}`, payload);
    } else {
      res = await ApiClient.post('/api/tasks', payload);
    }

    if (res.success) {
      UI.showToast(id ? 'Task updated successfully!' : 'Task created successfully!', 'success');
      UI.closeModal('taskModal');
      loadTasks();
    } else {
      UI.showToast(res.error || 'Operation failed', 'danger');
    }
  } catch (err) {
    UI.showToast('Network error while saving task', 'danger');
  } finally {
    UI.setButtonLoading(submitBtn, false);
  }
}

async function deleteTask(id) {
  const confirmed = await UI.confirm({
    title: 'Delete Task',
    message: 'Are you sure you want to delete this task?',
    confirmText: 'Delete Task',
    isDanger: true
  });
  if (!confirmed) return;

  const res = await ApiClient.delete(`/api/tasks/${id}`);
  if (res.success) {
    UI.showToast('Task deleted successfully', 'success');
    loadTasks();
  } else {
    UI.showToast(res.error || 'Failed to delete task', 'danger');
  }
}
