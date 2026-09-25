/**
 * CRM Reports & Business Intelligence Module
 * Fetches real database metrics from /api/reports and renders BI analytics.
 */

let currentDateFilter = 'month';
let currentStartDate = '';
let currentEndDate = '';
let activeReportPanel = 'salesPanel';

document.addEventListener('DOMContentLoaded', async () => {
  const user = await Auth.requireAuth();
  if (!user) return;

  UI.updateNotificationBadge();
  setupEventListeners();
  loadCurrentReport();
});

function setupEventListeners() {
  document.querySelectorAll('.date-preset-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.date-preset-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentDateFilter = btn.getAttribute('data-filter');
      currentStartDate = '';
      currentEndDate = '';
      document.getElementById('customStartDate').value = '';
      document.getElementById('customEndDate').value = '';
      loadCurrentReport();
    });
  });

  document.getElementById('applyCustomDateBtn')?.addEventListener('click', () => {
    const s = document.getElementById('customStartDate').value;
    const e = document.getElementById('customEndDate').value;
    if (!s && !e) {
      UI.showToast('Please select at least one date for custom filter', 'warning');
      return;
    }
    document.querySelectorAll('.date-preset-btn').forEach(b => b.classList.remove('active'));
    currentDateFilter = 'custom';
    currentStartDate = s;
    currentEndDate = e;
    loadCurrentReport();
  });
}

function switchReportTab(panelId, btn) {
  document.querySelectorAll('.report-tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.report-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  const panel = document.getElementById(panelId);
  if (panel) panel.classList.add('active');
  activeReportPanel = panelId;
  loadCurrentReport();
}

function getFilterParams() {
  const p = new URLSearchParams({ date_filter: currentDateFilter });
  if (currentStartDate) p.append('start_date', currentStartDate);
  if (currentEndDate) p.append('end_date', currentEndDate);
  return p.toString();
}

function loadCurrentReport() {
  switch (activeReportPanel) {
    case 'salesPanel': loadSalesReport(); break;
    case 'revenuePanel': loadRevenueReport(); break;
    case 'employeePanel': loadEmployeePerformance(); break;
    case 'customersPanel': loadCustomerReport(); break;
    case 'leadsPanel': loadLeadReport(); break;
    case 'tasksPanel': loadTaskReport(); break;
    case 'invoicesPanel': loadInvoiceReport(); break;
  }
}


// -------------------------------------------------------------
// 1. Sales Report
// -------------------------------------------------------------
async function loadSalesReport() {
  try {
    const res = await ApiClient.get(`/api/reports/sales?${getFilterParams()}`);
    if (!res.success) return;
    const { summary, stage_breakdown } = res.data.report;

    document.getElementById('salesTotalDeals').textContent = summary.total_deals;
    document.getElementById('salesWonValue').textContent = UI.formatCurrency(summary.won_deals_value);
    document.getElementById('salesWonCount').textContent = `${summary.won_deals_count} won deals`;
    document.getElementById('salesLostValue').textContent = UI.formatCurrency(summary.lost_deals_value);
    document.getElementById('salesLostCount').textContent = `${summary.lost_deals_count} lost deals`;
    document.getElementById('salesPipelineValue').textContent = UI.formatCurrency(summary.pipeline_value);
    document.getElementById('salesPipelineCount').textContent = `${summary.pipeline_deals_count} open deals`;

    const container = document.getElementById('salesStageBreakdown');
    if (stage_breakdown.length === 0) {
      container.innerHTML = '<div style="color: #718096; padding: 16px 0;">No deal data recorded for the selected period.</div>';
      return;
    }

    const maxVal = Math.max(...stage_breakdown.map(s => s.value), 1);
    container.innerHTML = stage_breakdown.map(s => {
      const pct = Math.round((s.value / maxVal) * 100);
      return `
        <div style="margin-bottom: 14px;">
          <div style="display: flex; justify-content: space-between; font-size: 0.9rem; font-weight: 600;">
            <span>${UI.escapeHtml(s.stage)} (${s.count} deals)</span>
            <span>${UI.formatCurrency(s.value)}</span>
          </div>
          <div class="progress-bar-container">
            <div class="progress-bar-fill" style="width: ${pct}%;"></div>
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load sales report', err);
  }
}

// -------------------------------------------------------------
// 2. Revenue Report
// -------------------------------------------------------------
async function loadRevenueReport() {
  try {
    const res = await ApiClient.get(`/api/reports/revenue?${getFilterParams()}`);
    if (!res.success) return;
    const { summary, method_breakdown, monthly_trend } = res.data.report;

    document.getElementById('revTotalCollected').textContent = UI.formatCurrency(summary.total_revenue);
    document.getElementById('revTotalCount').textContent = summary.total_transactions;
    document.getElementById('revAvgPayment').textContent = UI.formatCurrency(summary.average_payment);

    // Method breakdown
    const mContainer = document.getElementById('revMethodBreakdown');
    if (method_breakdown.length === 0) {
      mContainer.innerHTML = '<div style="color: #718096; padding: 16px 0;">No payments in selected period.</div>';
    } else {
      const maxTot = Math.max(...method_breakdown.map(m => m.total), 1);
      mContainer.innerHTML = method_breakdown.map(m => {
        const pct = Math.round((m.total / maxTot) * 100);
        return `
          <div style="margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.9rem; font-weight: 600;">
              <span style="text-transform: uppercase;">${UI.escapeHtml(m.method)} (${m.count})</span>
              <span>${UI.formatCurrency(m.total)}</span>
            </div>
            <div class="progress-bar-container">
              <div class="progress-bar-fill" style="width: ${pct}%; background: #2f855a;"></div>
            </div>
          </div>
        `;
      }).join('');
    }

    // Monthly trend
    const tContainer = document.getElementById('revMonthlyTrend');
    if (monthly_trend.length === 0) {
      tContainer.innerHTML = '<div style="color: #718096; padding: 16px 0;">No monthly trend available.</div>';
    } else {
      tContainer.innerHTML = `
        <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
          <thead>
            <tr style="border-bottom: 1px solid #edf2f7; text-align: left; color: #718096;">
              <th style="padding: 6px 0;">Month</th>
              <th style="padding: 6px 0; text-align: center;">Txns</th>
              <th style="padding: 6px 0; text-align: right;">Total</th>
            </tr>
          </thead>
          <tbody>
            ${monthly_trend.map(mt => `
              <tr style="border-bottom: 1px solid #f7fafc;">
                <td style="padding: 6px 0; font-weight: 600;">${mt.month}</td>
                <td style="padding: 6px 0; text-align: center;">${mt.count}</td>
                <td style="padding: 6px 0; text-align: right; font-weight: 600; color: #2f855a;">${UI.formatCurrency(mt.total)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }

  } catch (err) {
    console.error('Failed to load revenue report', err);
  }
}

// -------------------------------------------------------------
// 3. Customer Report
// -------------------------------------------------------------
async function loadCustomerReport() {
  try {
    const res = await ApiClient.get(`/api/reports/customers?${getFilterParams()}`);
    if (!res.success) return;
    const { summary, status_breakdown, industry_breakdown } = res.data.report;

    document.getElementById('custTotal').textContent = summary.total_customers;
    document.getElementById('custNew').textContent = summary.new_customers;

    const sContainer = document.getElementById('custStatusBreakdown');
    if (status_breakdown.length === 0) {
      sContainer.innerHTML = '<div style="color: #718096; padding: 16px 0;">No customers found.</div>';
    } else {
      sContainer.innerHTML = status_breakdown.map(s => `
        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #edf2f7; font-size: 0.9rem;">
          <span style="font-weight: 600; text-transform: capitalize;">${UI.escapeHtml(s.status)}</span>
          <span style="font-weight: 700; color: #073472;">${s.count}</span>
        </div>
      `).join('');
    }

    const iContainer = document.getElementById('custIndustryBreakdown');
    if (industry_breakdown.length === 0) {
      iContainer.innerHTML = '<div style="color: #718096; padding: 16px 0;">No industry data.</div>';
    } else {
      iContainer.innerHTML = industry_breakdown.map(i => `
        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #edf2f7; font-size: 0.9rem;">
          <span style="font-weight: 600;">${UI.escapeHtml(i.industry)}</span>
          <span style="font-weight: 700; color: #2b6cb0;">${i.count}</span>
        </div>
      `).join('');
    }

  } catch (err) {
    console.error('Failed to load customer report', err);
  }
}

// -------------------------------------------------------------
// 4. Lead Report
// -------------------------------------------------------------
async function loadLeadReport() {
  try {
    const res = await ApiClient.get(`/api/reports/leads?${getFilterParams()}`);
    if (!res.success) return;
    const { summary, status_breakdown, source_breakdown } = res.data.report;

    document.getElementById('leadTotal').textContent = summary.total_leads;
    document.getElementById('leadConvRate').textContent = `${summary.conversion_rate}%`;
    document.getElementById('leadConverted').textContent = summary.converted_leads;
    document.getElementById('leadOpen').textContent = summary.open_leads;

    const sContainer = document.getElementById('leadStatusBreakdown');
    if (status_breakdown.length === 0) {
      sContainer.innerHTML = '<div style="color: #718096; padding: 16px 0;">No leads found.</div>';
    } else {
      sContainer.innerHTML = status_breakdown.map(s => `
        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #edf2f7; font-size: 0.9rem;">
          <span style="font-weight: 600; text-transform: capitalize;">${UI.escapeHtml(s.status)}</span>
          <span style="font-weight: 700;">${s.count}</span>
        </div>
      `).join('');
    }

    const srcContainer = document.getElementById('leadSourceBreakdown');
    if (source_breakdown.length === 0) {
      srcContainer.innerHTML = '<div style="color: #718096; padding: 16px 0;">No source data.</div>';
    } else {
      srcContainer.innerHTML = source_breakdown.map(src => `
        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #edf2f7; font-size: 0.9rem;">
          <span style="font-weight: 600;">${UI.escapeHtml(src.source)}</span>
          <span style="font-weight: 700; color: #073472;">${src.count}</span>
        </div>
      `).join('');
    }

  } catch (err) {
    console.error('Failed to load lead report', err);
  }
}

// -------------------------------------------------------------
// 5. Task Report
// -------------------------------------------------------------
async function loadTaskReport() {
  try {
    const res = await ApiClient.get(`/api/reports/tasks?${getFilterParams()}`);
    if (!res.success) return;
    const { summary, priority_breakdown } = res.data.report;

    document.getElementById('taskTotal').textContent = summary.total_tasks;
    document.getElementById('taskPending').textContent = summary.pending_tasks;
    document.getElementById('taskInProgress').textContent = summary.in_progress_tasks;
    document.getElementById('taskCompleted').textContent = summary.completed_tasks;
    document.getElementById('taskOverdue').textContent = summary.overdue_tasks;

    const pContainer = document.getElementById('taskPriorityBreakdown');
    if (priority_breakdown.length === 0) {
      pContainer.innerHTML = '<div style="color: #718096; padding: 16px 0;">No tasks found.</div>';
    } else {
      pContainer.innerHTML = priority_breakdown.map(p => `
        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #edf2f7; font-size: 0.9rem;">
          <span style="font-weight: 600; text-transform: capitalize;">${UI.escapeHtml(p.priority)}</span>
          <span style="font-weight: 700;">${p.count}</span>
        </div>
      `).join('');
    }

  } catch (err) {
    console.error('Failed to load task report', err);
  }
}

// -------------------------------------------------------------
// 6. Invoice Report
// -------------------------------------------------------------
async function loadInvoiceReport() {
  try {
    const res = await ApiClient.get(`/api/reports/invoices?${getFilterParams()}`);
    if (!res.success) return;
    const { summary } = res.data.report;

    document.getElementById('invTotalCount').textContent = summary.total_invoices;
    document.getElementById('invTotalAmt').textContent = `${UI.formatCurrency(summary.total_invoiced_amount)} billed`;

    document.getElementById('invPaidCount').textContent = summary.paid_count;
    document.getElementById('invPaidAmt').textContent = `${UI.formatCurrency(summary.paid_amount)} collected`;

    document.getElementById('invPartialCount').textContent = summary.partially_paid_count;
    document.getElementById('invPartialAmt').textContent = `${UI.formatCurrency(summary.partially_paid_amount)} remaining`;

    document.getElementById('invOverdueCount').textContent = summary.overdue_count;
    document.getElementById('invOverdueAmt').textContent = `${UI.formatCurrency(summary.overdue_amount)} past due`;

  } catch (err) {
    console.error('Failed to load invoice report', err);
  }
}

// -------------------------------------------------------------
// 7. Employee Performance Report
// -------------------------------------------------------------
async function loadEmployeePerformance() {
  const tbody = document.getElementById('employeePerformanceBody');
  if (!tbody) return;

  UI.renderTableLoading(tbody, 7, 'Loading employee performance metrics...');

  try {
    const res = await ApiClient.get(`/api/reports/employee-performance?${getFilterParams()}`);
    if (!res.success || !res.data) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--danger); padding: 30px;">${UI.escapeHtml(res.message || 'Failed to load employee metrics')}</td></tr>`;
      return;
    }

    const performance = res.data.performance || [];
    if (performance.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 30px;">No staff records available</td></tr>';
      return;
    }

    // Top metrics
    const topProducer = performance[0] || {};
    const totalWonDeals = performance.reduce((sum, p) => sum + (p.won_deals || 0), 0);
    const totalTasksDone = performance.reduce((sum, p) => sum + (p.completed_tasks || 0), 0);

    if (document.getElementById('empTotalCount')) document.getElementById('empTotalCount').textContent = performance.length;
    if (document.getElementById('empTopRevenue')) document.getElementById('empTopRevenue').textContent = UI.formatCurrency(topProducer.revenue || 0);
    if (document.getElementById('empTopProducer')) document.getElementById('empTopProducer').textContent = topProducer.name ? `${topProducer.name} (${topProducer.won_deals || 0} won)` : '—';
    if (document.getElementById('empTotalWonDeals')) document.getElementById('empTotalWonDeals').textContent = totalWonDeals;
    if (document.getElementById('empTotalTasksDone')) document.getElementById('empTotalTasksDone').textContent = totalTasksDone;

    tbody.innerHTML = performance.map((p, idx) => {
      const initial = (p.name || 'U')[0].toUpperCase();
      const rankBadge = idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : `#${idx + 1}`;
      const winRate = p.deals > 0 ? Math.round((p.won_deals / p.deals) * 100) : 0;

      return `
        <tr>
          <td>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-weight: 700; width: 20px;">${rankBadge}</span>
              <div class="avatar" style="width: 28px; height: 28px; font-size: 0.8rem;">${initial}</div>
              <div>
                <strong>${UI.escapeHtml(p.name)}</strong>
                <div style="font-size: 0.75rem; color: var(--text-muted);">${UI.escapeHtml(p.email)}</div>
              </div>
            </div>
          </td>
          <td><span class="badge badge-secondary">${UI.escapeHtml(p.role)}</span></td>
          <td><strong>${p.won_deals || 0}</strong> <span style="font-size: 0.75rem; color: var(--text-muted);">/ ${p.deals || 0}</span></td>
          <td><strong style="color: var(--primary);">${UI.formatCurrency(p.revenue || 0)}</strong></td>
          <td><span class="badge badge-success">${p.completed_tasks || 0}</span> <span style="font-size: 0.75rem; color: var(--text-muted);">/ ${p.tasks || 0}</span></td>
          <td>${p.calls || 0} calls, ${p.meetings || 0} mtgs</td>
          <td>
            <div style="display: flex; align-items: center; gap: 6px;">
              <div class="progress-bar-container" style="flex: 1; height: 8px; margin: 0; min-width: 60px;">
                <div class="progress-bar-fill" style="width: ${winRate}%; background: ${winRate >= 50 ? 'var(--success)' : 'var(--primary)'};"></div>
              </div>
              <span style="font-size: 0.8rem; font-weight: 600;">${winRate}%</span>
            </div>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load employee performance', err);
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--danger); padding: 30px;">Error loading metrics</td></tr>`;
  }
}

