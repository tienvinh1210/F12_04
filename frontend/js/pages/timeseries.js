let tsPointSize = 3;
let tsShowTrend = false;

async function renderTimeseries(container) {
  const result = getQueryResult();
  if (!result || result.record_count === 0) {
    showEmptyState(container, getFilters());
    return;
  }
  showLoading(container);
  try {
    const filters = getFilters();
    const data = await apiFetch('/charts/timeseries', {
      method: 'POST',
      body: JSON.stringify({ ...filters, point_size: tsPointSize, show_smooth: tsShowTrend }),
    });
    let html = `
      <div class="alert alert-info">Tip: Click on legend items to toggle their visibility on the time series plot below.</div>`;
    if (result.common_filters_note) {
      html += `<div class="alert alert-muted">${result.common_filters_note}</div>`;
    }
    html += `
      <div class="controls-bar">
        <label>Point Size: <input type="range" id="ts-point-size" min="1" max="5" value="${tsPointSize}"> <span id="ts-point-val">${tsPointSize}</span></label>
        <label><input type="checkbox" id="ts-trend" ${tsShowTrend ? 'checked' : ''}> Show Trend Line</label>
      </div>
      <div class="chart-card"><h3>Time Series Plot</h3><div id="ts-chart" style="height:500px"></div></div>`;
    container.innerHTML = html;

    document.getElementById('ts-point-size').oninput = (e) => {
      tsPointSize = parseInt(e.target.value);
      document.getElementById('ts-point-val').textContent = tsPointSize;
      drawTimeseries(data);
    };
    document.getElementById('ts-trend').onchange = async (e) => {
      tsShowTrend = e.target.checked;
      const fresh = await apiFetch('/charts/timeseries', {
        method: 'POST',
        body: JSON.stringify({ ...getFilters(), point_size: tsPointSize, show_smooth: tsShowTrend }),
      });
      drawTimeseries(fresh);
    };
    drawTimeseries(data);
  } catch (err) {
    container.innerHTML = `<div class="alert alert-warning">${err.message}</div>`;
  }
}

function drawTimeseries(data) {
  const groups = [...new Set(data.series.map(s => s.group))];
  const traces = groups.map(g => {
    const pts = data.series.filter(s => s.group === g);
    const isTrend = g.includes('(trend)');
    return {
      x: pts.map(p => p.date),
      y: pts.map(p => p.value),
      name: g,
      type: 'scatter',
      mode: isTrend ? 'lines' : 'lines+markers',
      marker: { size: tsPointSize },
      line: { dash: isTrend ? 'dash' : 'solid' },
      hovertemplate: '%{fullData.name}<br>Date: %{x}<br>Avg: %{y:.2f}<extra></extra>',
    };
  });
  Plotly.newPlot('ts-chart', traces, {
    xaxis: { title: 'Date' },
    yaxis: { title: data.y_label },
    legend: { title: { text: 'Animal Group' } },
    margin: { t: 20 },
  }, { responsive: true });
}

window.renderTimeseries = renderTimeseries;
