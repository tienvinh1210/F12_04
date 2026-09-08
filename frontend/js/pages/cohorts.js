let cohortPercentile = 10;
let cohortData = null;

async function renderCohorts(container) {
  const result = getQueryResult();
  if (!result || result.record_count === 0) {
    showEmptyState(container, getFilters());
    return;
  }
  showLoading(container);
  try {
    cohortData = await apiFetch('/cohorts/analyze', {
      method: 'POST',
      body: JSON.stringify({ ...getFilters(), percentile: cohortPercentile }),
    });
    let html = `
      <div class="controls-bar">
        <label>Top/Bottom Percentile:
          <select id="cohort-pct">
            <option value="10" ${cohortPercentile === 10 ? 'selected' : ''}>10%</option>
            <option value="15" ${cohortPercentile === 15 ? 'selected' : ''}>15%</option>
            <option value="20" ${cohortPercentile === 20 ? 'selected' : ''}>20%</option>
          </select>
        </label>
      </div>`;
    if (cohortData.show_mixed_warning) {
      html += `<div class="alert alert-warning">You have selected both 'Overall' and specific items in your filters. Cohort rankings use the filtered dataset but group comparisons may be affected.</div>`;
    }
    html += `
      <div class="card explanation-card" style="margin-bottom:16px">
        <h3>How Individual Animal Ranking Works</h3>
        <p>Animals are ranked by their <strong>lifetime average</strong> of the selected measure across all dates in the filtered data.</p>
        <h4>How It Works</h4>
        <ul>
          <li>Each animal's average measure is calculated across all their records</li>
          <li>Animals are ranked from highest to lowest average</li>
          <li>Top cohort = highest performers at the selected percentile</li>
          <li>Bottom cohort = lowest performers at the selected percentile</li>
          <li>Timeline shows daily averages for cohort animals</li>
          <li>Use this to identify consistently high or low performers</li>
        </ul>
        <h4>Real-World Example</h4>
        <p>Animal A averages 650 kg while Animal B averages 520 kg over the same period — Animal A ranks in the top cohort.</p>
        <h4>Benefits for Your Farm</h4>
        <ul>
          <li>Identify top performers for breeding or retention decisions</li>
          <li>Spot underperformers early for intervention</li>
          <li>Track cohort trends over time via the timeline chart</li>
          <li>Export cohort lists for further analysis</li>
        </ul>
        <div class="alert alert-info" style="margin-top:8px">Tip: Click "View Animals" on cohort cards to see individual rankings, or use the timeline chart below.</div>
      </div>
      <div class="cohort-cards">
        ${cohortCard('top', cohortData.top, 'fa-trophy', 'Top Cohort — Individual Averages')}
        ${cohortCard('bottom', cohortData.bottom, 'fa-triangle-exclamation', 'Bottom Cohort — Individual Averages')}
      </div>
      <div class="chart-card"><h3>Cohort Timeline</h3><div id="cohort-timeline" style="height:400px"></div></div>
      <div id="cohort-modal" class="modal-overlay hidden" onclick="if(event.target===this)closeCohortModal()">
        <div class="modal"><h3 id="cohort-modal-title"></h3><div class="table-wrap"><table class="data-table" id="cohort-modal-table"></table></div>
        <button class="btn btn-secondary" style="margin-top:16px" onclick="closeCohortModal()">Close</button></div>
      </div>`;
    container.innerHTML = html;

    document.getElementById('cohort-pct').onchange = async (e) => {
      cohortPercentile = parseInt(e.target.value);
      renderCohorts(container);
    };
    drawCohortTimeline(cohortData);
  } catch (err) {
    container.innerHTML = `<div class="alert alert-warning">${err.message}</div>`;
  }
}

function cohortCard(type, data, icon, title) {
  const measure = getFilters().measure;
  return `<div class="card cohort-card ${type}">
    <h3><i class="fa ${icon}"></i> ${title}</h3>
    <p style="font-size:12px;color:var(--text-secondary);margin:8px 0">Based on each animal's overall average ${measure}</p>
    <div class="kpi-row">
      <div><strong>Avg:</strong> ${formatValue(data.average, measure)}</div>
      <div><strong>Min:</strong> ${formatValue(data.min, measure)}</div>
      <div><strong>Max:</strong> ${formatValue(data.max, measure)}</div>
      <div><strong>N:</strong> ${data.count}</div>
    </div>
    <div style="margin-top:12px;display:flex;gap:8px">
      <button class="btn btn-primary btn-sm" onclick="viewCohortAnimals('${type}')">View Animals</button>
      <button class="btn btn-secondary btn-sm" onclick="exportCohort('${type}')">Export</button>
    </div>
  </div>`;
}

function drawCohortTimeline(data) {
  const topPts = data.timeline.filter(t => t.cohort === 'top');
  const botPts = data.timeline.filter(t => t.cohort === 'bottom');
  Plotly.newPlot('cohort-timeline', [
    { x: topPts.map(p => p.date), y: topPts.map(p => p.value), name: 'Top Cohort', type: 'scatter', mode: 'lines' },
    { x: botPts.map(p => p.date), y: botPts.map(p => p.value), name: 'Bottom Cohort', type: 'scatter', mode: 'lines' },
  ], { xaxis: { title: 'Date' }, margin: { t: 20 } }, { responsive: true });
}

function viewCohortAnimals(type) {
  const data = cohortData[type];
  document.getElementById('cohort-modal-title').textContent = `${type === 'top' ? 'Top' : 'Bottom'} Cohort Animals`;
  const measure = getFilters().measure;
  document.getElementById('cohort-modal-table').innerHTML = `
    <thead><tr><th>EID</th><th>Avg ${measure}</th></tr></thead>
    <tbody>${data.animals.map(a => `<tr><td>${a.eid}</td><td>${formatValue(a.avg_measure, measure)}</td></tr>`).join('')}</tbody>`;
  document.getElementById('cohort-modal').classList.remove('hidden');
}

function closeCohortModal() {
  document.getElementById('cohort-modal')?.classList.add('hidden');
}

async function exportCohort(type) {
  const f = getFilters();
  const params = new URLSearchParams({ cohort: type, farm_id: f.farm_id, year: f.year, measure: f.measure, percentile: cohortPercentile });
  await apiDownload(`/cohorts/export.csv?${params}`, `cohort_${type}.csv`);
  showToast('Cohort exported', 'success');
}

window.renderCohorts = renderCohorts;
window.viewCohortAnimals = viewCohortAnimals;
window.closeCohortModal = closeCohortModal;
window.exportCohort = exportCohort;
