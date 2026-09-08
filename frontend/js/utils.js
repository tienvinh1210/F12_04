function showToast(message, type = 'info') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function showEmptyState(container, filters) {
  container.innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">📊</div>
      <h3>No Data Found</h3>
      <p>No livestock records match your current filter criteria.<br>Try adjusting your filters to see more data.</p>
      <div style="margin:16px 0;font-size:13px;text-align:left;max-width:300px;margin-inline:auto">
        <strong>Current filters:</strong><br>
        Year: ${filters.year}<br>
        Month: ${filters.month}<br>
        Day: ${filters.day}
      </div>
      <button class="btn btn-primary" onclick="clearAllFilters()">Reset All Filters</button>
    </div>
  `;
}

function formatValue(val, measure) {
  if (measure === 'animalvalue') return `$${Number(val).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
  const units = { finalpweight: 'kg', finalgrowthpbs: 'kg/day', methane: 'g/day', carcassweight: 'kg', feedintakekgd: 'kg/day', animalprod: 'units' };
  return `${Number(val).toFixed(2)} ${units[measure] || ''}`;
}

function showLoading(container) {
  container.innerHTML = '<div class="skeleton" style="height:400px"></div>';
}

window.showToast = showToast;
window.showEmptyState = showEmptyState;
window.formatValue = formatValue;
window.showLoading = showLoading;
