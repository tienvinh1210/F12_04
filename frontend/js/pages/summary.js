async function renderSummary(container) {
  if (!getFilters().year) {
    container.innerHTML = '<div class="alert alert-muted">Loading filters…</div>';
    return;
  }
  showLoading(container);
  try {
    const data = await apiFetch('/summary/stats', { method: 'POST', body: JSON.stringify(getFilters()) });
    if (typeof updateRecordCountBadge === 'function' && data.record_count != null) {
      updateRecordCountBadge(data.record_count);
    }
    if (!data.groups || data.groups.length === 0 || data.record_count === 0) {
      showEmptyState(container, getFilters());
      return;
    }
    const measure = getFilters().measure;
    let html = `<div class="alert alert-info">The summary statistics below show separate statistics for each animal group based on your current filter selections.</div>`;
    for (const group of data.groups) {
      html += `<h3 class="group-header">${group.full_group}</h3><div class="kpi-row">`;
      for (const [key, w] of Object.entries(group.windows)) {
        html += `
          <div class="kpi-card">
            <div class="kpi-label">${w.label}</div>
            <div class="kpi-value">${formatValue(w.mean, measure)}</div>
            <div style="font-size:12px;color:var(--text-secondary)">Mean</div>
            <hr style="margin:8px 0;border:none;border-top:1px solid var(--border)">
            <div class="kpi-stats">
              Min: ${formatValue(w.min, measure)}<br>
              Max: ${formatValue(w.max, measure)}<br>
              Median: ${formatValue(w.median, measure)}<br>
              Count: ${w.count}
            </div>
          </div>`;
      }
      html += '</div>';
    }
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div class="alert alert-warning">${err.message}</div>`;
  }
}

window.renderSummary = renderSummary;
