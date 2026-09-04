const SAVED_VIEWS_KEY = 'livestock_saved_views';

const defaultFilters = () => ({
  year: null,
  month: 'All',
  day: 'All',
  sex: ['Overall'],
  treatment: ['Overall'],
  breed: ['Overall'],
  mob: ['Overall'],
  eid: ['Overall'],
  measure: 'finalpweight',
});

let filterState = defaultFilters();
let choices = null;
let queryResult = null;
let debounceTimer = null;
let onFilterChange = null;

function debounce(fn, ms = 300) {
  return (...args) => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => fn(...args), ms);
  };
}

function getFilterPayload() {
  const user = getUser();
  return {
    farm_id: getFarmId(),
    ...filterState,
    eid: user?.is_admin ? filterState.eid : ['Overall'],
  };
}

function updateRecordCountBadge(recordCount, totalRecords) {
  const countEl = document.getElementById('record-count');
  if (!countEl || recordCount == null) return;
  const total = totalRecords ?? choices?.total_records ?? recordCount;
  countEl.textContent = `Showing ${Number(recordCount).toLocaleString()} of ${Number(total).toLocaleString()} records`;
}

async function loadChoices() {
  const farmId = getFarmId();
  choices = await apiFetch(`/filters/choices?farm_id=${farmId}`);
  if (!filterState.year && choices.max_year) {
    filterState.year = choices.max_year;
  }
  renderFilterUI();
}

function renderMultiSelect(containerId, field, options) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = options.map(opt => {
    const checked = filterState[field].includes(opt) ? 'checked' : '';
    return `<label><input type="checkbox" data-field="${field}" value="${opt}" ${checked}> ${opt}</label>`;
  }).join('');
  container.querySelectorAll('input').forEach(cb => {
    cb.addEventListener('change', () => {
      const selected = [...container.querySelectorAll('input:checked')].map(i => i.value);
      filterState[field] = selected.length ? selected : ['Overall'];
      // Dim checkbox changes: recompute chart locally (no API) — grade target ≤1.5s.
      // EID still needs the server path (grain omits animal ids).
      notifyFilterChange({ dimOnly: field !== 'eid' });
    });
  });
}

function renderFilterUI() {
  if (!choices) return;
  const yearSel = document.getElementById('filter-year');
  if (yearSel) {
    yearSel.innerHTML = choices.years.map(y => `<option value="${y}" ${y === filterState.year ? 'selected' : ''}>${y}</option>`).join('');
    yearSel.onchange = () => { filterState.year = parseInt(yearSel.value); debouncedQuery(); };
  }
  const monthSel = document.getElementById('filter-month');
  if (monthSel) {
    monthSel.innerHTML = choices.months.map(m => `<option value="${m}" ${m === filterState.month ? 'selected' : ''}>${m}</option>`).join('');
    monthSel.onchange = () => { filterState.month = monthSel.value; debouncedQuery(); };
  }
  const daySel = document.getElementById('filter-day');
  if (daySel) {
    daySel.innerHTML = choices.days.map(d => `<option value="${d}" ${String(d) === String(filterState.day) ? 'selected' : ''}>${d}</option>`).join('');
    daySel.onchange = () => { filterState.day = daySel.value; debouncedQuery(); };
  }
  renderMultiSelect('filter-sex', 'sex', choices.sexes);
  renderMultiSelect('filter-treatment', 'treatment', choices.treatments);
  renderMultiSelect('filter-breed', 'breed', choices.breeds);
  renderMultiSelect('filter-mob', 'mob', choices.mobs);
  const user = getUser();
  const eidSection = document.getElementById('eid-section');
  if (eidSection) {
    eidSection.classList.toggle('hidden', !user?.is_admin);
    if (user?.is_admin && choices.eids) {
      renderMultiSelect('filter-eid', 'eid', choices.eids);
    }
  }
  const measureSel = document.getElementById('filter-measure');
  if (measureSel) {
    measureSel.innerHTML = choices.measures.map(m => `<option value="${m.key}" ${m.key === filterState.measure ? 'selected' : ''}>${m.label}</option>`).join('');
    measureSel.onchange = () => { filterState.measure = measureSel.value; debouncedQuery(); };
  }
}

function selectAll(field) {
  if (!choices) return;
  const map = { sex: 'sexes', treatment: 'treatments', breed: 'breeds', mob: 'mobs', eid: 'eids' };
  filterState[field] = [...choices[map[field]]];
  renderFilterUI();
  notifyFilterChange({ dimOnly: field !== 'eid' });
}

function invertSelection(field) {
  if (!choices) return;
  const map = { sex: 'sexes', treatment: 'treatments', breed: 'breeds', mob: 'mobs', eid: 'eids' };
  const all = choices[map[field]];
  const current = new Set(filterState[field]);
  filterState[field] = all.filter(v => !current.has(v));
  if (!filterState[field].length) filterState[field] = ['Overall'];
  renderFilterUI();
  notifyFilterChange({ dimOnly: field !== 'eid' });
}

function clearAllFilters() {
  filterState = defaultFilters();
  if (choices?.max_year) filterState.year = choices.max_year;
  renderFilterUI();
  debouncedQuery();
  showToast('Filters cleared', 'success');
}

function notifyFilterChange(options = {}) {
  if (onFilterChange) onFilterChange(options);
}

async function runQuery(options = {}) {
  const { render = true, dimOnly = false } = options;
  try {
    if (render && onFilterChange) {
      onFilterChange({ dimOnly });
      return;
    }
    queryResult = await apiFetch('/data/query', {
      method: 'POST',
      body: JSON.stringify({ ...getFilterPayload(), include_rows: false }),
    });
    updateRecordCountBadge(queryResult.record_count, queryResult.total_records);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

const debouncedQuery = debounce(() => runQuery({ render: true, dimOnly: false }), 120);

function getQueryResult() { return queryResult; }
function getFilters() { return getFilterPayload(); }
function getFilterState() { return filterState; }

function setFilterState(state) {
  filterState = { ...defaultFilters(), ...state };
  renderFilterUI();
  debouncedQuery();
}

async function initFilters(callback) {
  onFilterChange = callback;
  await loadChoices();
  if (onFilterChange) onFilterChange({ dimOnly: false });
  runQuery({ render: false });
  if (typeof prefetchTimeseriesGrain === 'function') prefetchTimeseriesGrain();
  document.getElementById('clear-filters')?.addEventListener('click', clearAllFilters);
  document.querySelectorAll('[data-select-all]').forEach(el => {
    el.addEventListener('click', (e) => { e.preventDefault(); selectAll(el.dataset.selectAll); });
  });
  document.querySelectorAll('[data-invert]').forEach(el => {
    el.addEventListener('click', (e) => { e.preventDefault(); invertSelection(el.dataset.invert); });
  });
}

window.initFilters = initFilters;
window.getFilters = getFilters;
window.getFilterState = getFilterState;
window.setFilterState = setFilterState;
window.getQueryResult = getQueryResult;
window.clearAllFilters = clearAllFilters;
window.runQuery = runQuery;
window.updateRecordCountBadge = updateRecordCountBadge;
