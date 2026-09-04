let tsPointSize = 3;
let tsShowTrend = false;
let tsRequestId = 0;
let tsAbort = null;
let tsShellReady = false;
let tsLastData = null;

function ensureTimeseriesShell(container, data) {
  if (tsShellReady && container.querySelector('#ts-chart')) {
    const note = container.querySelector('#ts-filters-note');
    const cov = container.querySelector('#ts-coverage');
    if (note) {
      note.classList.toggle('hidden', !data.common_filters_note);
      note.textContent = data.common_filters_note || '';
    }
    if (cov) {
      const c = data.combo_coverage;
      if (c && c.expected > 1) {
        cov.classList.remove('hidden');
        if (c.missing > 0) {
          const preview = (c.missing_groups || []).slice(0, 6).map(g => `<li>${g}</li>`).join('');
          const more = c.missing > 6 ? `<li>…and ${c.missing - 6} more</li>` : '';
          cov.className = 'alert alert-warning';
          cov.innerHTML = `Showing <strong>${c.present}</strong> of <strong>${c.expected}</strong> selected combinations
            (${c.missing} have no matching records in the data).
            <details style="margin-top:8px"><summary>Combinations with no data</summary>
              <ul style="margin:8px 0 0 18px;font-size:12px">${preview}${more}</ul>
            </details>`;
        } else {
          cov.className = 'alert alert-muted';
          cov.textContent = `Showing all ${c.present} selected combinations.`;
        }
      } else {
        cov.classList.add('hidden');
        cov.innerHTML = '';
      }
    }
    return;
  }

  let html = `
    <div class="alert alert-info">Tip: Click on legend items to toggle their visibility on the time series plot below.</div>
    <div id="ts-filters-note" class="alert alert-muted ${data.common_filters_note ? '' : 'hidden'}">${data.common_filters_note || ''}</div>
    <div id="ts-coverage" class="hidden"></div>
    <div class="controls-bar">
      <label>Point Size: <input type="range" id="ts-point-size" min="1" max="5" value="${tsPointSize}"> <span id="ts-point-val">${tsPointSize}</span></label>
      <label><input type="checkbox" id="ts-trend" ${tsShowTrend ? 'checked' : ''}> Show Trend Line</label>
    </div>
    <div class="chart-card"><h3>Time Series Plot</h3><div id="ts-chart" style="height:500px"></div></div>`;
  container.innerHTML = html;
  tsShellReady = true;

  const covEl = container.querySelector('#ts-coverage');
  if (covEl) {
    const c = data.combo_coverage;
    if (c && c.expected > 1) {
      covEl.classList.remove('hidden');
      if (c.missing > 0) {
        const preview = (c.missing_groups || []).slice(0, 6).map(g => `<li>${g}</li>`).join('');
        const more = c.missing > 6 ? `<li>…and ${c.missing - 6} more</li>` : '';
        covEl.className = 'alert alert-warning';
        covEl.innerHTML = `Showing <strong>${c.present}</strong> of <strong>${c.expected}</strong> selected combinations
          (${c.missing} have no matching records in the data).
          <details style="margin-top:8px"><summary>Combinations with no data</summary>
            <ul style="margin:8px 0 0 18px;font-size:12px">${preview}${more}</ul>
          </details>`;
      } else {
        covEl.className = 'alert alert-muted';
        covEl.textContent = `Showing all ${c.present} selected combinations.`;
      }
    }
  }

  document.getElementById('ts-point-size').oninput = (e) => {
    tsPointSize = parseInt(e.target.value);
    document.getElementById('ts-point-val').textContent = tsPointSize;
    if (tsLastData) drawTimeseries(tsLastData);
  };
  document.getElementById('ts-trend').onchange = async (e) => {
    tsShowTrend = e.target.checked;
    await renderTimeseries(container, { soft: true });
  };
}

async function renderTimeseries(container, options = {}) {
  const soft = !!options.soft;
  if (!getFilters().year) {
    container.innerHTML = '<div class="alert alert-muted">Loading filters…</div>';
    tsShellReady = false;
    return;
  }

  const reqId = ++tsRequestId;
  if (tsAbort) tsAbort.abort();
  tsAbort = new AbortController();

  if (!soft && !tsShellReady) {
    showLoading(container);
  } else if (soft || tsShellReady) {
    const chart = container.querySelector('#ts-chart');
    if (chart && !chart.dataset.loading) {
      chart.style.opacity = '0.55';
      chart.dataset.loading = '1';
    }
  }

  try {
    const filters = getFilters();
    const data = await apiFetch('/charts/timeseries', {
      method: 'POST',
      body: JSON.stringify({ ...filters, point_size: tsPointSize, show_smooth: tsShowTrend }),
      signal: tsAbort.signal,
    });
    if (reqId !== tsRequestId) return;

    if (typeof updateRecordCountBadge === 'function' && data.record_count != null) {
      updateRecordCountBadge(data.record_count);
    }
    if (!data.series || data.series.length === 0) {
      tsShellReady = false;
      showEmptyState(container, filters);
      return;
    }

    tsLastData = data;
    ensureTimeseriesShell(container, data);
    drawTimeseries(data);
    const chart = container.querySelector('#ts-chart');
    if (chart) {
      chart.style.opacity = '1';
      delete chart.dataset.loading;
    }
  } catch (err) {
    if (err.name === 'AbortError' || reqId !== tsRequestId) return;
    tsShellReady = false;
    container.innerHTML = `<div class="alert alert-warning">${err.message}</div>`;
  }
}

function buildTimeseriesTraces(data) {
  const groups = [...new Set(data.series.map(s => s.group))];
  return groups.map(g => {
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
}

function drawTimeseries(data) {
  const traces = buildTimeseriesTraces(data);
  const allY = data.series.filter(s => !String(s.group).includes('(trend)')).map(s => s.value);
  let yRange;
  if (allY.length) {
    const ymin = Math.min(...allY);
    const ymax = Math.max(...allY);
    const pad = Math.max((ymax - ymin) * 0.08, 5);
    yRange = [ymin - pad, ymax + pad];
  }

  const layout = {
    xaxis: { title: 'Date', type: 'date' },
    yaxis: {
      title: data.y_label,
      rangemode: 'normal',
      ...(yRange ? { range: yRange } : {}),
    },
    legend: { title: { text: 'Animal Group' } },
    margin: { t: 20, r: 20 },
    hovermode: 'closest',
  };
  const opts = { responsive: true, displayModeBar: true };
  const el = document.getElementById('ts-chart');
  if (!el) return;
  if (el.data) {
    Plotly.react(el, traces, layout, opts);
  } else {
    Plotly.newPlot(el, traces, layout, opts);
  }
}

function resetTimeseriesShell() {
  tsShellReady = false;
  tsLastData = null;
}

window.renderTimeseries = renderTimeseries;
window.resetTimeseriesShell = resetTimeseriesShell;
