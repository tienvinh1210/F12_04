let histBins = 20;

async function renderDistributions(container) {
  if (!getFilters().year) {
    container.innerHTML = '<div class="alert alert-muted">Loading filters…</div>';
    return;
  }
  showLoading(container);
  try {
    const data = await apiFetch('/charts/distribution', {
      method: 'POST',
      body: JSON.stringify({ ...getFilters(), hist_bins: histBins }),
    });
    if (typeof updateRecordCountBadge === 'function' && data.record_count != null) {
      updateRecordCountBadge(data.record_count);
    }
    if (!data.boxplot?.groups?.length) {
      showEmptyState(container, getFilters());
      return;
    }
    let html = `
      <div class="alert alert-info">Tip: Click on legend items to toggle their visibility on the graphs below.</div>
      <div class="controls-bar">
        <label>Histogram Bins: <input type="range" id="hist-bins" min="10" max="50" step="5" value="${histBins}"> <span id="hist-bins-val">${histBins}</span></label>
      </div>
      <div class="chart-grid-2">
        <div class="chart-card"><h3>Histogram Comparison</h3><div id="hist-chart" style="height:400px"></div></div>
        <div class="chart-card"><h3>Box Plot</h3><div id="box-chart" style="height:400px"></div></div>
      </div>`;
    container.innerHTML = html;
    document.getElementById('hist-bins').oninput = async (e) => {
      histBins = parseInt(e.target.value);
      document.getElementById('hist-bins-val').textContent = histBins;
      const fresh = await apiFetch('/charts/distribution', {
        method: 'POST',
        body: JSON.stringify({ ...getFilters(), hist_bins: histBins }),
      });
      drawDistributions(fresh);
    };
    drawDistributions(data);
  } catch (err) {
    container.innerHTML = `<div class="alert alert-warning">${err.message}</div>`;
  }
}

function drawDistributions(data) {
  const histTraces = data.histogram.groups.map(g => ({
    x: g.values,
    name: g.group,
    type: 'histogram',
    opacity: 0.6,
    nbinsx: data.histogram.bins,
  }));
  const shapes = [
    { type: 'line', x0: data.histogram.mean, x1: data.histogram.mean, y0: 0, y1: 1, yref: 'paper', line: { color: '#B08968', dash: 'dash' } },
    { type: 'line', x0: data.histogram.median, x1: data.histogram.median, y0: 0, y1: 1, yref: 'paper', line: { color: '#7B241C', dash: 'dot' } },
  ];
  Plotly.newPlot('hist-chart', histTraces, {
    barmode: 'overlay',
    shapes,
    margin: { t: 20 },
  }, { responsive: true });

  const boxTraces = data.boxplot.groups.map(g => ({
    y: [g.min, g.q1, g.median, g.q3, g.max],
    name: g.group,
    type: 'box',
    boxpoints: false,
  }));
  Plotly.newPlot('box-chart', boxTraces, { margin: { t: 20 } }, { responsive: true });
}

window.renderDistributions = renderDistributions;
