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
    if (data.common_filters_note && data.common_filters_note !== result.common_filters_note) {
      html += `<div class="alert alert-muted">${data.common_filters_note}</div>`;
    }
    const cov = data.combo_coverage;
    if (cov && cov.expected > 1) {
      if (cov.missing > 0) {
        const preview = (cov.missing_groups || []).slice(0, 6).map(g => `<li>${g}</li>`).join('');
        const more = cov.missing > 6 ? `<li>…and ${cov.missing - 6} more</li>` : '';
        html += `<div class="alert alert-warning">
          Showing <strong>${cov.present}</strong> of <strong>${cov.expected}</strong> selected combinations
          (${cov.missing} have no matching records in the data).
          <details style="margin-top:8px"><summary>Combinations with no data</summary>
            <ul style="margin:8px 0 0 18px;font-size:12px">${preview}${more}</ul>
          </details>
        </div>`;
      } else {
        html += `<div class="alert alert-muted">Showing all ${cov.present} selected combinations.</div>`;
      }
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
    const pts = data.series
      .filter(s => s.group === g)
      .slice()
      .sort((a, b) => a.date.localeCompare(b.date));
    const isTrend = g.includes('(trend)');
    const vals = pts.map(p => p.value);
    const span = vals.length ? Math.max(...vals) - Math.min(...vals) : 0;
    return {
      x: pts.map(p => p.date),
      y: vals,
      customdata: pts.map(p => p.count),
      name: g,
      type: 'scatter',
      mode: isTrend ? 'lines' : 'lines+markers',
      marker: { size: Math.max(tsPointSize, span < 30 ? 5 : tsPointSize) },
      line: { dash: isTrend ? 'dash' : 'solid', width: isTrend ? 2 : 2.5, shape: 'linear' },
      connectgaps: false,
      hovertemplate:
        '%{fullData.name}<br>Date: %{x}<br>Avg: %{y:.2f}<br>Records: %{customdata}<extra></extra>',
    };
  });

  // Pad Y range slightly so gradual series (e.g. Brahman X ~25 kg span) remain readable
  const allY = data.series.filter(s => !String(s.group).includes('(trend)')).map(s => s.value);
  let yRange;
  if (allY.length) {
    const ymin = Math.min(...allY);
    const ymax = Math.max(...allY);
    const pad = Math.max((ymax - ymin) * 0.08, 5);
    yRange = [ymin - pad, ymax + pad];
  }

  Plotly.newPlot('ts-chart', traces, {
    xaxis: { title: 'Date', type: 'date' },
    yaxis: {
      title: data.y_label,
      rangemode: 'normal',
      ...(yRange ? { range: yRange } : {}),
    },
    legend: { title: { text: 'Animal Group' } },
    margin: { t: 20, r: 20 },
    hovermode: 'closest',
  }, { responsive: true, displayModeBar: true });
}

window.renderTimeseries = renderTimeseries;
