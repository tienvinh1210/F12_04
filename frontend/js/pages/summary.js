let summaryRequestId = 0;

function fullGroupLabel(combo, isAdmin) {
  const parts = ['sex', 'treatment', 'breed', 'mob'].map(
    (col) => `${grainFriendlyLabel(col)}: ${combo[col] || 'Overall'}`
  );
  parts.push(`EID: ${isAdmin ? (combo.eid || 'Overall') : '*****'}`);
  return parts.join(', ');
}

function pad2(n) {
  return String(n).padStart(2, '0');
}

function formatDayLabel(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number);
  return `${pad2(d)}/${pad2(m)}/${y}`;
}

function addDaysIso(isoDate, deltaDays) {
  const dt = new Date(`${isoDate}T00:00:00Z`);
  dt.setUTCDate(dt.getUTCDate() + deltaDays);
  return dt.toISOString().slice(0, 10);
}

function kpiFromRows(rows, label, unit) {
  if (!rows.length) {
    return { mean: 0, min: 0, max: 0, median: 0, count: 0, unit, label };
  }
  let totalC = 0;
  let wsum = 0;
  let minV = null;
  let maxV = null;
  const dailyMeans = [];
  for (const r of rows) {
    const c = r.c | 0;
    const v = +r.v;
    totalC += c;
    wsum += v * c;
    dailyMeans.push(v);
    const mn = r.mn != null ? +r.mn : v;
    const mx = r.mx != null ? +r.mx : v;
    minV = minV == null ? mn : Math.min(minV, mn);
    maxV = maxV == null ? mx : Math.max(maxV, mx);
  }
  dailyMeans.sort((a, b) => a - b);
  const mid = Math.floor(dailyMeans.length / 2);
  let med = 0;
  if (dailyMeans.length) {
    med = dailyMeans.length % 2
      ? dailyMeans[mid]
      : (dailyMeans[mid - 1] + dailyMeans[mid]) / 2;
  }
  return {
    mean: totalC ? Math.round((wsum / totalC) * 100) / 100 : 0,
    min: Math.round((minV || 0) * 100) / 100,
    max: Math.round((maxV || 0) * 100) / 100,
    median: Math.round(med * 100) / 100,
    count: totalC,
    unit,
    label,
  };
}

function assembleSummaryFromGrain(grain, filters) {
  if (typeof filterGrainByMonthDay === 'function') {
    grain = filterGrainByMonthDay(grain, filters);
  }
  const isAdmin = !!getUser()?.is_admin;
  const dims = {
    sex: expandFilterDim(filters.sex),
    treatment: expandFilterDim(filters.treatment),
    breed: expandFilterDim(filters.breed),
    mob: expandFilterDim(filters.mob),
    eid: ['Overall'],
  };
  const allOverall = Object.values(dims).every((v) => v.length === 1 && v[0] === 'Overall');
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

  const groups = [];
  for (const combo of combos) {
    const matched = grain.filter((row) => grainRowMatchesCombo(row, combo));
    if (!matched.length) continue;
    const maxD = matched.reduce((m, r) => (r.d > m ? r.d : m), matched[0].d);
    const start15 = addDaysIso(maxD, -14);
    const start31 = addDaysIso(maxD, -30);
    const lastDay = matched.filter((r) => r.d === maxD);
    const last15 = matched.filter((r) => r.d >= start15);
    const last31 = matched.filter((r) => r.d >= start31);
    groups.push({
      full_group: fullGroupLabel(combo, isAdmin),
      windows: {
        last_day: kpiFromRows(lastDay, `Last Day (${formatDayLabel(maxD)})`, ''),
        last_15_days: kpiFromRows(last15, 'Last 15 Days', ''),
        last_month: kpiFromRows(last31, 'Last Month', ''),
        overall: kpiFromRows(matched, 'Overall', ''),
      },
    });
  }

  if (groups.length === 1 && allOverall) {
    groups[0].full_group = fullGroupLabel(
      { sex: 'Overall', treatment: 'Overall', breed: 'Overall', mob: 'Overall', eid: 'Overall' },
      isAdmin,
    );
  }

  const recordCount = grain.reduce((sum, r) => sum + (r.c | 0), 0);
  return { groups, record_count: recordCount };
}

function paintSummary(container, data) {
  if (typeof updateRecordCountBadge === 'function' && data.record_count != null) {
    updateRecordCountBadge(data.record_count);
  }
  if (!data.groups || !data.groups.length || data.record_count === 0) {
    showEmptyState(container, getFilters());
    return;
  }
  const measure = getFilters().measure;
  let html = `<div class="alert alert-info">The summary statistics below show separate statistics for each animal group based on your current filter selections.</div>`;
  for (const group of data.groups) {
    html += `<h3 class="group-header">${group.full_group}</h3><div class="kpi-row">`;
    for (const w of Object.values(group.windows)) {
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
}

async function renderSummary(container, options = {}) {
  const dimOnly = !!options.dimOnly;
  if (!getFilters().year) {
    container.innerHTML = '<div class="alert alert-muted">Loading filters…</div>';
    return;
  }

  const eidActive = !!(getUser()?.is_admin && (getFilters().eid || ['Overall']).some((v) => v !== 'Overall'));
  const cache = typeof getScopeGrainCache === 'function' ? getScopeGrainCache() : null;
  const scopeOk = cache && cache.key === tsScopeKey(getFilters());

  // Checkbox path: recompute KPIs in the browser from cached grain.
  if (!eidActive && (dimOnly || scopeOk) && cache && scopeOk) {
    paintSummary(container, assembleSummaryFromGrain(cache.grain, getFilters()));
    return;
  }

  const reqId = ++summaryRequestId;
  if (!dimOnly || !container.querySelector('.kpi-card')) {
    showLoading(container);
  }

  try {
    const filters = getFilters();
    let data;
    if (eidActive) {
      data = await apiFetch('/summary/stats', { method: 'POST', body: JSON.stringify(filters) });
    } else {
      await ensureScopeGrain(filters);
      if (reqId !== summaryRequestId) return;
      if (typeof scheduleMeasureGrainPrefetch === 'function') scheduleMeasureGrainPrefetch();
      const fresh = getScopeGrainCache();
      data = assembleSummaryFromGrain(fresh.grain, filters);
    }
    if (reqId !== summaryRequestId) return;
    paintSummary(container, data);
  } catch (err) {
    if (reqId !== summaryRequestId) return;
    container.innerHTML = `<div class="alert alert-warning">${err.message}</div>`;
  }
}

window.renderSummary = renderSummary;
