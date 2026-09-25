/**
 * CRM Dashboard Module
 * Fetches dynamic metrics from /api/dashboard/summary and binds to DOM elements.
 * Displays customers, leads, pipeline value, pending tasks, today's calls, meetings,
 * and live activity stream with zero fake static numbers.
 */

let currentDashboardRange = 'this_month';

document.addEventListener('DOMContentLoaded', async () => {
  if (typeof Auth !== 'undefined') {
    const user = await Auth.requireAuth();
    if (!user) return;
  }

  const rangeSelect = document.getElementById('dashboardDateRange');
  if (rangeSelect) {
    rangeSelect.value = currentDashboardRange;
    rangeSelect.addEventListener('change', () => {
      currentDashboardRange = rangeSelect.value;
      loadDashboardData(currentDashboardRange);
    });
  }

  loadDashboardData(currentDashboardRange);
});

async function loadDashboardData(range = 'this_month') {
  const metricGrid = document.querySelector('.metrics-grid');
  const activityContainer = document.getElementById('recentActivityContainer');
  const followupsContainer = document.getElementById('scheduledFollowupsContainer');

  try {
    const res = await ApiClient.get(`/api/dashboard/summary?range=${encodeURIComponent(range)}`);
    if (!res.success || !res.data || !res.data.summary) {
      if (typeof UI !== 'undefined') {
        UI.showToast(res.error || 'Failed to fetch dashboard metrics', 'danger');
      }
      return;

    }

    const s = res.data.summary;

    UI.updateNotificationBadge();

    // Render Metrics Grid
    if (metricGrid) {
      metricGrid.innerHTML = `
        <div class="metric-card">
          <div class="metric-header">
            <span class="metric-title">Total Customers</span>
            <span class="metric-badge positive">+${s.new_customers_30d || 0} new</span>
          </div>
          <div class="metric-value">${(s.total_customers || 0).toLocaleString()}</div>
          <div class="metric-subtext">Registered client accounts</div>
        </div>

        <div class="metric-card">
          <div class="metric-header">
            <span class="metric-title">Active Leads</span>
            <span class="metric-badge positive">+${s.new_leads_30d || 0} new</span>
          </div>
          <div class="metric-value">${(s.total_leads || 0).toLocaleString()}</div>
          <div class="metric-subtext">Sales pipeline opportunities</div>
        </div>

        <div class="metric-card">
          <div class="metric-header">
            <span class="metric-title">Total Revenue</span>
            <span class="metric-badge positive">${s.won_deals || 0} Won Deals</span>
          </div>
          <div class="metric-value" style="color: #2f855a;">${UI.formatCurrency(s.total_revenue || 0)}</div>
          <div class="metric-subtext">Collected remittances</div>
        </div>

        <div class="metric-card">
          <div class="metric-header">
            <span class="metric-title">Outstanding Receivables</span>
            <span class="metric-badge neutral">${s.total_invoices || 0} Invoices</span>
          </div>
          <div class="metric-value" style="color: #dd6b20;">${UI.formatCurrency(s.pending_payments || 0)}</div>
          <div class="metric-subtext">Pending client payments</div>
        </div>

        <div class="metric-card">
          <div class="metric-header">
            <span class="metric-title">Products Catalog</span>
            <span class="metric-badge neutral">Active</span>
          </div>
          <div class="metric-value">${(s.total_products || 0).toLocaleString()}</div>
          <div class="metric-subtext">Catalog products / services</div>
        </div>

        <div class="metric-card">
          <div class="metric-header">
            <span class="metric-title">Pending Tasks</span>
            <span class="metric-badge neutral">${s.today_calls || 0} Calls Today</span>
          </div>
          <div class="metric-value">${(s.pending_tasks || 0).toLocaleString()}</div>
          <div class="metric-subtext">${s.upcoming_meetings || 0} scheduled meetings</div>
        </div>
      `;
    }

    // Render Activity Feed
    if (activityContainer) {
      if (!s.recent_activities || s.recent_activities.length === 0) {
        activityContainer.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">📋</div>
            <div class="empty-state-text">No activity records yet</div>
            <div class="empty-state-subtext">Actions in Customers, Leads, and Deals will appear here automatically.</div>
          </div>
        `;
      } else {
        activityContainer.innerHTML = s.recent_activities.map(act => {
          const userTag = act.user_name ? UI.escapeHtml(act.user_name) : 'System';
          const timeTag = UI.formatDateTime(act.created_at);
          return `
            <div class="timeline-item">
              <div class="timeline-dot"></div>
              <div class="timeline-body">
                <div class="timeline-header">
                  <span class="timeline-title">${UI.escapeHtml(act.action)}</span>
                  <span class="timeline-time">${timeTag}</span>
                </div>
                <div class="timeline-desc">
                  ${UI.escapeHtml(act.description || '')}
                  <div style="margin-top: 4px; font-size: 0.75rem; color: var(--text-muted);">By ${userTag}</div>
                </div>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // Render Pipeline Breakdown & Follow-ups
    if (followupsContainer) {
      const dealsBreakdown = s.deal_pipeline_breakdown || [];
      const leadsBreakdown = s.lead_status_breakdown || [];

      let html = '<div style="display: flex; flex-direction: column; gap: 16px;">';

      // Deals Stage Summary
      html += '<div><h4 style="font-size: 0.8rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px;">Deals by Stage</h4>';
      if (dealsBreakdown.length === 0) {
        html += '<p style="font-size: 0.85rem; color: var(--text-secondary);">No deals in pipeline.</p>';
      } else {
        dealsBreakdown.forEach(item => {
          html += `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--border-color); font-size: 0.85rem;">
              <span style="text-transform: capitalize; font-weight: 500;">${UI.escapeHtml(item.stage)}</span>
              <span><strong>${item.count}</strong> (${UI.formatCurrency(item.total_value)})</span>
            </div>
          `;
        });
      }
      html += '</div>';

      // Leads Status Summary
      html += '<div><h4 style="font-size: 0.8rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px;">Leads by Status</h4>';
      if (leadsBreakdown.length === 0) {
        html += '<p style="font-size: 0.85rem; color: var(--text-secondary);">No leads logged yet.</p>';
      } else {
        leadsBreakdown.forEach(item => {
          html += `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--border-color); font-size: 0.85rem;">
              <span style="text-transform: capitalize; font-weight: 500;">${UI.escapeHtml(item.status)}</span>
              <span class="badge badge-info">${item.count}</span>
            </div>
          `;
        });
      }
      html += '</div></div>';

      followupsContainer.innerHTML = html;
    }

    // Render Lead Conversion Funnel
    const funnelContainer = document.getElementById('conversionFunnelContainer');
    if (funnelContainer) {
      const funnel = res.data.conversion_funnel || [];
      if (funnel.length === 0) {
        funnelContainer.innerHTML = '<div class="empty-state"><div class="empty-state-text">No funnel data available</div></div>';
      } else {
        funnelContainer.innerHTML = `
          <div class="funnel-container">
            ${funnel.map(step => `
              <div class="funnel-row">
                <div class="funnel-label">${UI.escapeHtml(step.stage)}</div>
                <div class="funnel-track">
                  <div class="funnel-fill" style="width: ${Math.max(8, step.percentage)}%; background: ${step.color || 'var(--primary)'};">
                    ${step.percentage}%
                  </div>
                </div>
                <div class="funnel-val">${step.count.toLocaleString()}</div>
              </div>
            `).join('')}
          </div>
        `;
      }
    }

    // Render 6-Month Monthly Revenue Trend
    const trendContainer = document.getElementById('revenueTrendContainer');
    if (trendContainer) {
      const trend = res.data.revenue_trend || [];
      if (trend.length === 0) {
        trendContainer.innerHTML = '<div class="empty-state"><div class="empty-state-text">No remittance history</div></div>';
      } else {
        const maxVal = Math.max(...trend.map(t => t.amount), 1);
        trendContainer.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: flex-end; height: 160px; padding: 20px 10px 10px 10px; gap: 8px;">
            ${trend.map(t => {
              const heightPct = Math.max(12, Math.round((t.amount / maxVal) * 100));
              return `
                <div style="flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end;">
                  <span style="font-size: 0.7rem; font-weight: 700; color: var(--text-primary); margin-bottom: 4px;">
                    ${t.amount > 0 ? (t.amount >= 1000 ? '₹' + (t.amount/1000).toFixed(1) + 'k' : '₹' + t.amount) : '₹0'}
                  </span>
                  <div style="width: 100%; max-width: 44px; height: ${heightPct}%; background: linear-gradient(180deg, var(--primary) 0%, #3b82f6 100%); border-radius: 6px 6px 0 0;" title="${t.month_label}: ${UI.formatCurrency(t.amount)}"></div>
                  <span style="font-size: 0.72rem; color: var(--text-muted); margin-top: 6px; white-space: nowrap;">
                    ${t.month_label.split(' ')[0]}
                  </span>
                </div>
              `;
            }).join('')}
          </div>
        `;
      }
    }

    // Render Top Sales Reps Leaderboard
    const repsContainer = document.getElementById('topSalesRepsContainer');
    if (repsContainer) {
      const reps = res.data.top_sales_reps || [];
      if (reps.length === 0) {
        repsContainer.innerHTML = '<div class="empty-state"><div class="empty-state-text">No sales records in selected period</div></div>';
      } else {
        repsContainer.innerHTML = `
          <table class="data-table" style="font-size: 0.85rem;">
            <thead>
              <tr>
                <th>Representative</th>
                <th>Won Deals</th>
                <th>Total Value</th>
              </tr>
            </thead>
            <tbody>
              ${reps.map((rep, idx) => `
                <tr>
                  <td>
                    <div style="display: flex; align-items: center; gap: 8px;">
                      <span style="font-weight: 700; color: var(--text-muted); width: 16px;">#${idx + 1}</span>
                      <div class="avatar" style="width: 26px; height: 26px; font-size: 0.75rem;">${(rep.name || 'U')[0]}</div>
                      <div>
                        <strong>${UI.escapeHtml(rep.name)}</strong>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">${UI.escapeHtml(rep.email)}</div>
                      </div>
                    </div>
                  </td>
                  <td><span class="badge badge-success">${rep.won_deals} Won</span></td>
                  <td><strong style="color: var(--primary);">${UI.formatCurrency(rep.revenue)}</strong></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      }
    }

    // Render Payment Status Breakdown
    const payStatusContainer = document.getElementById('paymentStatusBreakdownContainer');
    if (payStatusContainer) {
      const breakdown = res.data.payment_status_breakdown || [];
      if (breakdown.length === 0) {
        payStatusContainer.innerHTML = '<div class="empty-state"><div class="empty-state-text">No invoices generated yet</div></div>';
      } else {
        payStatusContainer.innerHTML = `
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; padding: 6px 0;">
            ${breakdown.map(b => `
              <div style="background: #f8fafc; border: 1px solid var(--border-color); border-radius: 8px; padding: 12px;">
                <div style="font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: var(--text-muted); margin-bottom: 4px;">
                  ${UI.escapeHtml(b.status)}
                </div>
                <div style="font-size: 1.15rem; font-weight: 700; color: var(--text-primary); margin-bottom: 2px;">
                  ${b.count}
                </div>
                <div style="font-size: 0.75rem; color: var(--text-secondary);">
                  ${UI.formatCurrency(b.total_amount)}
                </div>
              </div>
            `).join('')}
          </div>
        `;
      }
    }

  } catch (err) {
    console.error('Error loading dashboard data:', err);
  }
}

