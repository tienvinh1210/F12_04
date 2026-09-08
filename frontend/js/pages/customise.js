async function renderCustomise(container) {
  container.innerHTML = `
    <h2>Customise Chart</h2>
    <p style="color:var(--text-secondary);margin-bottom:16px">Build your own chart — filters from the sidebar do not apply on this page.</p>
    <div class="card" style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
      <div class="form-group"><label>Chart Type</label>
        <select id="custom-type"><option value="line">Line</option><option value="bar">Bar</option><option value="scatter">Scatter</option><option value="area">Area</option><option value="hist">Histogram</option><option value="box">Box Plot</option></select>
      </div>
      <div class="form-group"><label>Title</label><input type="text" id="custom-title" value="Custom Chart"></div>
      <div class="form-group"><label>X Axis</label>
        <select id="custom-x"><option value="date">Date</option><option value="sex">Sex</option><option value="breed">Breed</option><option value="mob">Mob</option></select>
      </div>
      <div class="form-group"><label>Y Axis / Measure</label>
        <select id="custom-y"><option value="finalpweight">Final processed weight</option><option value="finalgrowthpbs">Final growth PBS</option><option value="methane">Methane</option><option value="animalvalue">Animal value</option><option value="carcassweight">Carcass weight</option><option value="feedintakekgd">Feed intake</option></select>
      </div>
      <div class="form-group"><label>Group By</label>
        <select id="custom-group"><option value="sex">Sex</option><option value="breed">Breed</option><option value="mob">Mob</option><option value="treatment">Treatment</option><option value="">None</option></select>
      </div>
      <div class="form-group"><label>Aggregation</label>
        <select id="custom-agg"><option value="mean">Mean</option><option value="sum">Sum</option><option value="count">Count</option><option value="min">Min</option><option value="max">Max</option></select>
      </div>
    </div>
    <button class="btn btn-primary" id="custom-preview">Update Preview</button>
    <div class="chart-card" style="margin-top:16px"><div id="custom-chart" style="height:450px"></div></div>`;

  document.getElementById('custom-preview').onclick = previewCustom;
  previewCustom();
}

async function previewCustom() {
  const filters = getFilters();
  const body = {
    ...filters,
    chart_type: document.getElementById('custom-type').value,
    title: document.getElementById('custom-title').value,
    x_col: document.getElementById('custom-x').value,
    y_col: document.getElementById('custom-y').value,
    group_col: document.getElementById('custom-group').value || null,
    agg_fun: document.getElementById('custom-agg').value,
  };
  try {
    const data = await apiFetch('/charts/custom', { method: 'POST', body: JSON.stringify(body) });
    Plotly.newPlot('custom-chart', data.data, data.layout, { responsive: true });
  } catch (err) {
    showToast(err.message, 'error');
  }
}

window.renderCustomise = renderCustomise;
