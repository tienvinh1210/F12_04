let tablePage = 1;
const PAGE_SIZE = 50;

async function renderDataManagement(container) {
  const result = getQueryResult();
  if (!result || result.record_count === 0) {
    showEmptyState(container, getFilters());
    return;
  }
  showLoading(container);
  try {
    const data = await apiFetch('/data/query', {
      method: 'POST',
      body: JSON.stringify({ ...getFilters(), include_rows: true, page: tablePage, page_size: PAGE_SIZE }),
    });
    const cols = ['date', 'eid', 'sex', 'breed', 'treatment', 'mob', getFilters().measure];
    let html = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <h2>Data Management</h2>
        <button class="btn btn-primary" id="export-csv"><i class="fa fa-download"></i> Download CSV</button>
      </div>
      <div class="table-wrap card">
        <table class="data-table">
          <thead><tr>${cols.map(c => `<th>${c}</th>`).join('')}</tr></thead>
          <tbody>${data.filtered.map(row => `<tr>${cols.map(c => `<td>${row[c] ?? row.treatment_display ?? ''}</td>`).join('')}</tr>`).join('')}</tbody>
        </table>
      </div>
      <div style="margin-top:12px;display:flex;gap:8px;align-items:center">
        <button class="btn btn-secondary btn-sm" id="prev-page" ${tablePage <= 1 ? 'disabled' : ''}>Previous</button>
        <span>Page ${tablePage} (${data.record_count} total records)</span>
        <button class="btn btn-secondary btn-sm" id="next-page" ${tablePage * PAGE_SIZE >= data.record_count ? 'disabled' : ''}>Next</button>
      </div>`;
    container.innerHTML = html;

    document.getElementById('export-csv').onclick = async () => {
      const f = getFilters();
      const params = new URLSearchParams({
        farm_id: f.farm_id, year: f.year, month: f.month, day: f.day,
        sex: f.sex.join('|'), treatment: f.treatment.join('|'),
        breed: f.breed.join('|'), mob: f.mob.join('|'), eid: f.eid.join('|'),
      });
      await apiDownload(`/data/export.csv?${params}`, `${f.farm_id}_export.csv`);
      showToast('CSV downloaded', 'success');
    };
    document.getElementById('prev-page')?.addEventListener('click', () => { tablePage--; renderDataManagement(container); });
    document.getElementById('next-page')?.addEventListener('click', () => { tablePage++; renderDataManagement(container); });
  } catch (err) {
    container.innerHTML = `<div class="alert alert-warning">${err.message}</div>`;
  }
}

window.renderDataManagement = renderDataManagement;
