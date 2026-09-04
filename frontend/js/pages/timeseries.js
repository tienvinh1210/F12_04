let tsPointSize = 3;
let tsShowTrend = false;
let tsRequestId = 0;
let tsAbort = null;
let tsShellReady = false;
let tsLastData = null;
let tsGrainCache = null; // { key, grain, y_label, record_count }
let tsPrefetchPromise = null;
let tsGrainInflight = null; // { key, promise }

function tsScopeKey(filters) {
  return [filters.farm_id, filters.year, filters.month || 'All', String(filters.day || 'All'), filters.measure].join('|');
}

function expandDim(selected) {
  selected = selected && selected.length ? selected : ['Overall'];
  const hasAll = selected.includes('Overall');
  const specifics = selected.filter(v => v !== 'Overall');
  if (hasAll && !specifics.length) return ['Overall'];
  if (hasAll && specifics.length) return ['Overall', ...specifics];
  if (specifics.length) return specifics;
  return ['Overall'];
}

function friendlyLabel(col) {
  if (col === 'treatment') return 'Treatment';
  if (col === 'eid') return 'EID';
  if (col === 'sex') return 'Sex';
  if (col === 'breed') return 'Breed';
  if (col === 'mob') return 'Mob';
  return col;
}

function labelFromCombo(combo, varying, allOverall) {
  if (allOverall || !varying.length) {
    if (Object.values(combo).every(v => v === 'Overall')) return 'Overall Average';
    const parts = ['sex', 'treatment', 'breed', 'mob', 'eid']
      .filter(d => combo[d] && combo[d] !== 'Overall')
      .map(d => `${friendlyLabel(d)}: ${combo[d]}`);
    return parts.length ? parts.join(' | ') : 'Overall Average';
  }
  return varying.map(d => `${friendlyLabel(d)}: ${combo[d]}`).join(' | ');
}

function rowMatchesCombo(row, combo) {
  if (combo.sex !== 'Overall' && row.s !== combo.sex) return false;
  if (combo.treatment !== 'Overall' && row.t !== combo.treatment) return false;
  if (combo.breed !== 'Overall' && row.b !== combo.breed) return false;
  if (combo.mob !== 'Overall' && row.m !== combo.mob) return false;
  return true;
}

function smoothSeries(series) {
  const byGroup = {};
  for (const row of series) {
    if (String(row.group).includes('(trend)')) continue;
    (byGroup[row.group] ||= []).push(row);
  }
  const extra = [];
  for (const [group, pts] of Object.entries(byGroup)) {
    pts.sort((a, b) => a.date.localeCompare(b.date));
    if (pts.length < 3) continue;
    const window = Math.max(3, Math.min(15, Math.floor(pts.length / 5) || 3));
    const values = pts.map(p => p.value);
    pts.forEach((p, i) => {
      const lo = Math.max(0, i - Math.floor(window / 2));
      const hi = Math.min(values.length, i + Math.floor(window / 2) + 1);
      const chunk = values.slice(lo, hi);
      const avg = chunk.reduce((a, b) => a + b, 0) / chunk.length;
      extra.push({ date: p.date, group: `${group} (trend)`, value: Math.round(avg * 100) / 100, count: p.count });
    });
  }
  return series.concat(extra);
}

function assembleTimeseriesFromGrain(grain, filters, yLabel, showSmooth) {
  const dims = {
    sex: expandDim(filters.sex),
    treatment: expandDim(filters.treatment),
    breed: expandDim(filters.breed),
    mob: expandDim(filters.mob),
    eid: ['Overall'],
  };
  const varying = Object.keys(dims).filter(d => dims[d].length > 1);
  const allOverall = Object.values(dims).every(v => v.length === 1 && v[0] === 'Overall');
  const combos = [];
  for (const sex of dims.sex) {
    for (const treatment of dims.treatment) {
      for (const breed of dims.breed) {
        for (const mob of dims.mob) {
          combos.push({ sex, treatment, breed, mob, eid: 'Overall' });
        }
      }
    }
  }

  const series = [];
  const present = [];
  const missing = [];
  let recordCount = 0;

  for (const combo of combos) {
    const label = labelFromCombo(combo, varying, allOverall);
    const buckets = new Map();
    for (const row of grain) {
      if (!rowMatchesCombo(row, combo)) continue;
      const c = row.c | 0;
      const v = +row.v;
      recordCount += c;
      const cur = buckets.get(row.d) || { w: 0, c: 0 };
      cur.w += v * c;
      cur.c += c;
      buckets.set(row.d, cur);
    }
    if (!buckets.size) {
      missing.push(label);
      continue;
    }
    present.push(label);
    for (const d of [...buckets.keys()].sort()) {
      const b = buckets.get(d);
      series.push({
        date: d,
        group: label,
        value: b.c ? Math.round((b.w / b.c) * 100) / 100 : 0,
        count: b.c,
      });
    }
  }

  // recordCount above double-counts when Overall+specifics overlap; use grain total instead
  const grainCount = grain.reduce((sum, r) => sum + (r.c | 0), 0);

  let outSeries = series;
  if (showSmooth) outSeries = smoothSeries(series);

  let note = null;
  if (present.length > 1 && varying.length) {
    note = varying.length === 1
      ? `Comparing groups by ${friendlyLabel(varying[0])} only`
      : `Comparing groups by ${varying.map(friendlyLabel).join(', ')}`;
  }

  return {
    series: outSeries,
    y_label: yLabel,
    combo_coverage: {
      expected: combos.length,
      present: present.length,
      missing: missing.length,
      present_groups: present,
      missing_groups: missing,
    },
    common_filters_note: note,
    record_count: grainCount,
  };
}

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

  container.innerHTML = `
    <div class="alert alert-info">Tip: Click on legend items to toggle their visibility on the time series plot below.</div>
    <div id="ts-filters-note" class="alert alert-muted ${data.common_filters_note ? '' : 'hidden'}">${data.common_filters_note || ''}</div>
    <div id="ts-coverage" class="hidden"></div>
    <div class="controls-bar">
      <label>Point Size: <input type="range" id="ts-point-size" min="1" max="5" value="${tsPointSize}"> <span id="ts-point-val">${tsPointSize}</span></label>
      <label><input type="checkbox" id="ts-trend" ${tsShowTrend ? 'checked' : ''}> Show Trend Line</label>
    </div>
    <div class="chart-card"><h3>Time Series Plot</h3><div id="ts-chart" style="height:500px"></div></div>`;
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
  document.getElementById('ts-trend').onchange = (e) => {
    tsShowTrend = e.target.checked;
    applyTimeseriesFromCache(container);
  };
}

function applyTimeseriesFromCache(container) {
  if (!tsGrainCache) return false;
  const filters = getFilters();
  if (tsGrainCache.key !== tsScopeKey(filters)) return false;
  const data = assembleTimeseriesFromGrain(
    tsGrainCache.grain,
    filters,
    tsGrainCache.y_label,
    tsShowTrend,
  );
  if (typeof updateRecordCountBadge === 'function') {
    updateRecordCountBadge(data.record_count);
  }
  if (!data.series.length) {
    tsShellReady = false;
    showEmptyState(container, filters);
    return true;
  }
  tsLastData = data;
  ensureTimeseriesShell(container, data);
  drawTimeseries(data);
  return true;
}

async function ensureTimeseriesGrain(filters, signal) {
  const key = tsScopeKey(filters);
  if (tsGrainCache && tsGrainCache.key === key) return tsGrainCache;

  // EID comparisons still need the server timeseries path (grain omits eid).
  const eid = filters.eid || ['Overall'];
  if (getUser()?.is_admin && eid.some(v => v !== 'Overall')) {
    return null;
  }

  if (tsGrainInflight && tsGrainInflight.key === key) {
    return tsGrainInflight.promise;
  }

  const promise = (async () => {
    const payload = await apiFetch('/charts/timeseries-grain', {
      method: 'POST',
      body: JSON.stringify({
        farm_id: filters.farm_id,
        year: filters.year,
        month: filters.month,
        day: filters.day,
        measure: filters.measure,
        sex: ['Overall'],
        treatment: ['Overall'],
        breed: ['Overall'],
        mob: ['Overall'],
        eid: ['Overall'],
      }),
      signal,
    });
    tsGrainCache = {
      key,
      grain: payload.grain || [],
      y_label: payload.y_label,
      record_count: payload.record_count,
    };
    return tsGrainCache;
  })();

  tsGrainInflight = { key, promise };
  try {
    return await promise;
  } finally {
    if (tsGrainInflight && tsGrainInflight.promise === promise) tsGrainInflight = null;
  }
}

async function prefetchTimeseriesGrain() {
  const filters = getFilters();
  if (!filters.year) return;
  try {
    tsPrefetchPromise = ensureTimeseriesGrain(filters);
    await tsPrefetchPromise;
  } catch {
    /* ignore prefetch errors */
  } finally {
    tsPrefetchPromise = null;
  }
}

async function renderTimeseries(container, options = {}) {
  const dimOnly = !!options.dimOnly;
  if (!getFilters().year) {
    container.innerHTML = '<div class="alert alert-muted">Loading filters…</div>';
    tsShellReady = false;
    return;
  }

  // Checkbox / dim-only changes: recompute locally — target << 1.5s (usually <100ms).
  const eidActive = !!(getUser()?.is_admin && (getFilters().eid || ['Overall']).some(v => v !== 'Overall'));
  if (dimOnly && !eidActive && applyTimeseriesFromCache(container)) {
    return;
  }
  if (!eidActive && tsGrainCache && tsGrainCache.key === tsScopeKey(getFilters()) && applyTimeseriesFromCache(container)) {
    return;
  }

  const reqId = ++tsRequestId;
  if (tsAbort) tsAbort.abort();
  tsAbort = new AbortController();

  if (!tsShellReady) showLoading(container);
  else {
    const chart = container.querySelector('#ts-chart');
    if (chart) {
      chart.style.opacity = '0.55';
      chart.dataset.loading = '1';
    }
  }

  try {
    const filters = getFilters();
    const eid = filters.eid || ['Overall'];
    const needsEid = !!(getUser()?.is_admin && eid.some(v => v !== 'Overall'));

    let data;
    if (needsEid) {
      data = await apiFetch('/charts/timeseries', {
        method: 'POST',
        body: JSON.stringify({ ...filters, point_size: tsPointSize, show_smooth: tsShowTrend }),
        signal: tsAbort.signal,
      });
    } else {
      if (tsPrefetchPromise) await tsPrefetchPromise;
      await ensureTimeseriesGrain(filters, tsAbort.signal);
      if (reqId !== tsRequestId) return;
      data = assembleTimeseriesFromGrain(
        tsGrainCache.grain,
        filters,
        tsGrainCache.y_label,
        tsShowTrend,
      );
    }
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
  if (el.data) Plotly.react(el, traces, layout, opts);
  else Plotly.newPlot(el, traces, layout, opts);
}

function resetTimeseriesShell() {
  tsShellReady = false;
  tsLastData = null;
}

window.renderTimeseries = renderTimeseries;
window.resetTimeseriesShell = resetTimeseriesShell;
window.prefetchTimeseriesGrain = prefetchTimeseriesGrain;
window.ensureScopeGrain = ensureTimeseriesGrain;
window.getScopeGrainCache = () => tsGrainCache;
window.tsScopeKey = tsScopeKey;
window.expandFilterDim = expandDim;
window.grainRowMatchesCombo = rowMatchesCombo;
window.grainFriendlyLabel = friendlyLabel;
window.grainLabelFromCombo = labelFromCombo;
