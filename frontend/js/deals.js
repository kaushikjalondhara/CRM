/**
 * CRM Deals & Sales Pipeline Kanban Module
 * Handles Kanban stage board visualization, stage updates, deal creation/editing, and customer linking.
 */

const PIPELINE_STAGES = [
  { id: 'new', label: 'New', color: '#64748b' },
  { id: 'qualification', label: 'Qualification', color: '#0284c7' },
  { id: 'proposal', label: 'Proposal', color: '#d97706' },
  { id: 'negotiation', label: 'Negotiation', color: '#7c3aed' },
  { id: 'won', label: 'Closed Won', color: '#16a34a' },
  { id: 'lost', label: 'Closed Lost', color: '#dc2626' }
];

document.addEventListener('DOMContentLoaded', async () => {
  if (typeof Auth !== 'undefined') {
    const user = await Auth.requireAuth();
    if (!user) return;
  }

  loadKanbanBoard();
  initDealEvents();
});

function initDealEvents() {
  const addBtn = document.getElementById('addDealBtn');
  if (addBtn) {
    addBtn.addEventListener('click', async () => {
      resetDealForm();
      document.getElementById('dealModalTitle').textContent = 'Create New Deal';
      await loadCustomerSelectOptions('dealCustomerId');
      await UI.loadAssignees('dealAssignedTo');
      UI.openModal('dealModal');
    });
  }

  const form = document.getElementById('dealForm');
  if (form) {
    form.addEventListener('submit', handleDealFormSubmit);
  }
}

async function loadKanbanBoard() {
  const boardEl = document.getElementById('kanbanBoard');
  if (!boardEl) return;

  boardEl.innerHTML = '<div style="padding: 24px; color: var(--text-muted);">Loading sales pipeline...</div>';

  try {
    const res = await ApiClient.get('/api/deals/pipeline');
    if (!res.success || !res.data) {
      boardEl.innerHTML = `<div style="padding: 24px; color: var(--danger);">${UI.escapeHtml(res.error || 'Failed to load pipeline')}</div>`;
      return;
    }

    const { stages, stage_totals } = res.data;

    boardEl.innerHTML = PIPELINE_STAGES.map(stage => {
      const dealsInStage = (stages && stages[stage.id]) ? stages[stage.id] : [];
      const totalValue = (stage_totals && stage_totals[stage.id]) ? stage_totals[stage.id] : 0;
      const count = dealsInStage.length;

      return `
        <div class="kanban-column" data-stage="${stage.id}">
          <div class="kanban-col-header" style="border-bottom-color: ${stage.color};">
            <div class="kanban-col-title">
              <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${stage.color};"></span>
              <span>${stage.label}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span class="kanban-col-count">${count}</span>
            </div>
          </div>
          <div style="padding: 4px 16px 8px 16px; font-size: 0.75rem; color: var(--text-muted); background: white; border-bottom: 1px solid var(--border-color);">
            Value: <strong>${UI.formatCurrency(totalValue)}</strong>
          </div>

          <div class="kanban-col-body kanban-cards" id="stageCol-${stage.id}"
               ondragover="handleDealDragOver(event)"
               ondragleave="handleDealDragLeave(event)"
               ondrop="handleDealDrop(event, '${stage.id}')"
               data-stage="${stage.id}">
            ${dealsInStage.length === 0 ? `
              <div style="text-align: center; padding: 24px 10px; color: var(--text-muted); font-size: 0.8rem;">
                No deals in ${stage.label}
              </div>
            ` : dealsInStage.map(d => renderDealCard(d)).join('')}
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load Kanban board:', err);
  }
}

let draggedDealId = null;

function handleDealDragStart(e, dealId) {
  draggedDealId = dealId;
  e.dataTransfer.setData('text/plain', String(dealId));
  e.dataTransfer.effectAllowed = 'move';
  const card = document.getElementById(`dealCard-${dealId}`);
  if (card) {
    setTimeout(() => card.classList.add('dragging'), 0);
  }
}

function handleDealDragEnd(e) {
  const card = document.querySelector('.deal-card.dragging');
  if (card) card.classList.remove('dragging');
  document.querySelectorAll('.kanban-cards').forEach(el => el.classList.remove('drag-over'));
}

function handleDealDragOver(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  const container = e.currentTarget;
  if (!container.classList.contains('drag-over')) {
    container.classList.add('drag-over');
  }
}

function handleDealDragLeave(e) {
  e.currentTarget.classList.remove('drag-over');
}

async function handleDealDrop(e, targetStage) {
  e.preventDefault();
  e.currentTarget.classList.remove('drag-over');
  const dealId = draggedDealId || e.dataTransfer.getData('text/plain');
  if (!dealId) return;

  // Optimistic UI move
  const card = document.getElementById(`dealCard-${dealId}`);
  if (card && e.currentTarget) {
    e.currentTarget.appendChild(card);
    const stageSelect = card.querySelector('.stage-select');
    if (stageSelect) stageSelect.value = targetStage;
  }

  await updateDealStage(dealId, targetStage);
}

function renderDealCard(deal) {
  const customerName = deal.company_name
    ? `${deal.company_name} (${deal.customer_first_name || ''} ${deal.customer_last_name || ''})`
    : `${deal.customer_first_name || ''} ${deal.customer_last_name || ''}`;

  const assigned = deal.assigned_first_name ? `${deal.assigned_first_name} ${deal.assigned_last_name || ''}` : 'Unassigned';

  return `
    <div class="deal-card" id="dealCard-${deal.id}" draggable="true"
         ondragstart="handleDealDragStart(event, ${deal.id})"
         ondragend="handleDealDragEnd(event)">
      <div class="deal-card-header">
        <div class="deal-card-title">${UI.escapeHtml(deal.title)}</div>
        <div class="table-actions">
          <button class="action-btn" onclick="editDeal(${deal.id})" title="Edit Deal">✏</button>
          <button class="action-btn btn-danger" onclick="deleteDeal(${deal.id})" title="Delete Deal">🗑</button>
        </div>
      </div>
      <div class="deal-card-customer">
        👤 <a href="customer-details.html?id=${deal.customer_id}" style="color:inherit; text-decoration:underline;">${UI.escapeHtml(customerName)}</a>
      </div>
      <div class="deal-card-amount">
        ${UI.formatCurrency(deal.value)}
      </div>
      <div class="deal-card-footer">
        <span title="Assigned Rep">👤 ${UI.escapeHtml(assigned)}</span>
        <select class="stage-select" onchange="updateDealStage(${deal.id}, this.value)">
          ${PIPELINE_STAGES.map(s => `
            <option value="${s.id}" ${s.id === deal.stage ? 'selected' : ''}>${s.label}</option>
          `).join('')}
        </select>
      </div>
    </div>
  `;
}

async function updateDealStage(id, newStage) {
  try {
    const res = await ApiClient.put(`/api/deals/${id}/stage`, { stage: newStage });
    if (res.success) {
      UI.showToast(`Deal moved to ${newStage.toUpperCase()} successfully!`, 'success');
      loadKanbanBoard();
    } else {
      UI.showToast(res.error || 'Failed to update stage', 'danger');
      loadKanbanBoard();
    }
  } catch (err) {
    UI.showToast('Error updating deal stage', 'danger');
    loadKanbanBoard();
  }
}


async function loadCustomerSelectOptions(selectId, selectedId = null) {
  const sel = document.getElementById(selectId);
  if (!sel) return;

  sel.innerHTML = '<option value="">Loading customers...</option>';
  try {
    const res = await ApiClient.get('/api/customers?per_page=100');
    if (res.success && res.data && res.data.customers) {
      sel.innerHTML = '<option value="">-- Select Customer --</option>';
      res.data.customers.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        const name = `${c.first_name || ''} ${c.last_name || ''}`.trim();
        opt.textContent = c.company_name ? `${c.company_name} — ${name}` : name;
        if (selectedId && String(selectedId) === String(c.id)) {
          opt.selected = true;
        }
        sel.appendChild(opt);
      });
    }
  } catch (err) {
    sel.innerHTML = '<option value="">Failed to load customers</option>';
  }
}

function resetDealForm() {
  const form = document.getElementById('dealForm');
  if (form) form.reset();
  document.getElementById('dealId').value = '';
}

async function editDeal(id) {
  try {
    const res = await ApiClient.get(`/api/deals/${id}`);
    if (!res.success || !res.data || !res.data.deal) {
      UI.showToast(res.error || 'Failed to load deal', 'danger');
      return;
    }

    const d = res.data.deal;
    document.getElementById('dealId').value = d.id;
    document.getElementById('dealTitle').value = d.title || '';
    document.getElementById('dealValue').value = d.value || '';
    document.getElementById('dealStage').value = d.stage || 'new';
    document.getElementById('dealProbability').value = d.probability || 0;
    document.getElementById('dealExpectedCloseDate').value = d.expected_close_date ? d.expected_close_date.split('T')[0] : '';

    await loadCustomerSelectOptions('dealCustomerId', d.customer_id);
    await UI.loadAssignees('dealAssignedTo', d.assigned_to);

    document.getElementById('dealModalTitle').textContent = 'Edit Deal';
    UI.openModal('dealModal');
  } catch (err) {
    UI.showToast('Error fetching deal details', 'danger');
  }
}

async function handleDealFormSubmit(e) {
  e.preventDefault();

  const id = document.getElementById('dealId').value;
  const payload = {
    customer_id: parseInt(document.getElementById('dealCustomerId').value),
    title: document.getElementById('dealTitle').value.trim(),
    value: parseFloat(document.getElementById('dealValue').value) || 0,
    stage: document.getElementById('dealStage').value,
    probability: parseInt(document.getElementById('dealProbability').value) || 0,
    expected_close_date: document.getElementById('dealExpectedCloseDate').value || null,
    assigned_to: document.getElementById('dealAssignedTo').value || null,
  };

  if (!payload.customer_id || !payload.title) {
    UI.showToast('Customer and Deal Title are required.', 'warning');
    return;
  }

  const submitBtn = document.querySelector('#dealForm button[type="submit"]');
  UI.setButtonLoading(submitBtn, true, 'Saving...');

  try {
    let res;
    if (id) {
      res = await ApiClient.put(`/api/deals/${id}`, payload);
    } else {
      res = await ApiClient.post('/api/deals', payload);
    }

    if (res.success) {
      UI.showToast(id ? 'Deal updated successfully!' : 'Deal created successfully!', 'success');
      UI.closeModal('dealModal');
      loadKanbanBoard();
    } else {
      UI.showToast(res.error || 'Operation failed', 'danger');
    }
  } catch (err) {
    UI.showToast('Network error while saving deal', 'danger');
  } finally {
    UI.setButtonLoading(submitBtn, false);
  }
}

async function deleteDeal(id) {
  const confirmed = await UI.confirm({
    title: 'Delete Deal',
    message: 'Are you sure you want to delete this deal opportunity from the pipeline?',
    confirmText: 'Delete Deal',
    isDanger: true
  });
  if (!confirmed) return;

  const res = await ApiClient.delete(`/api/deals/${id}`);
  if (res.success) {
    UI.showToast('Deal deleted successfully', 'success');
    loadKanbanBoard();
  } else {
    UI.showToast(res.error || 'Failed to delete deal', 'danger');
  }
}

if (typeof window !== 'undefined') {
  window.handleDealDragStart = handleDealDragStart;
  window.handleDealDragEnd = handleDealDragEnd;
  window.handleDealDragOver = handleDealDragOver;
  window.handleDealDragLeave = handleDealDragLeave;
  window.handleDealDrop = handleDealDrop;
  window.updateDealStage = updateDealStage;
}

