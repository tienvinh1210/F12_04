function getUser() {
  const raw = sessionStorage.getItem('user');
  return raw ? JSON.parse(raw) : null;
}

function setSession(data) {
  sessionStorage.setItem('access_token', data.access_token);
  sessionStorage.setItem('user', JSON.stringify(data.user));
}

function logout() {
  sessionStorage.removeItem('access_token');
  sessionStorage.removeItem('user');
  sessionStorage.removeItem('boot_cache');
  window.location.href = '/login.html';
}

function requireAuth() {
  if (!sessionStorage.getItem('access_token')) {
    window.location.href = '/login.html';
    return false;
  }
  return true;
}

function getFarmId() {
  const params = new URLSearchParams(window.location.search);
  const user = getUser();
  return params.get('farm') || (user?.farms?.[0]?.farm_id) || 'KF';
}

const BOOT_CACHE_KEY = 'boot_cache';
const BOOT_CACHE_TTL_MS = 120000;

async function buildBootCache(token, farmId) {
  const apiBase = typeof API_BASE !== 'undefined' ? API_BASE : '/api';
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
  const choicesRes = await fetch(`${apiBase}/filters/choices?farm_id=${encodeURIComponent(farmId)}`, { headers });
  if (!choicesRes.ok) throw new Error('Failed to load filters');
  const choices = await choicesRes.json();
  const year = choices.max_year || (choices.years && choices.years[0]);
  const measure = 'finalpweight';
  let grainPayload = null;
  if (year) {
    const grainRes = await fetch(`${apiBase}/charts/timeseries-grain`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        farm_id: farmId,
        year,
        month: 'All',
        day: 'All',
        measure,
        sex: ['Overall'],
        treatment: ['Overall'],
        breed: ['Overall'],
        mob: ['Overall'],
        eid: ['Overall'],
      }),
    });
    if (grainRes.ok) grainPayload = await grainRes.json();
  }
  const boot = {
    ts: Date.now(),
    farm_id: farmId,
    choices,
    grain: grainPayload,
    grain_key: grainPayload ? [farmId, year, measure].join('|') : null,
  };
  try {
    sessionStorage.setItem(BOOT_CACHE_KEY, JSON.stringify(boot));
  } catch (_) {
    /* quota — dashboard will refetch */
  }
  return boot;
}

function takeBootCache() {
  try {
    const raw = sessionStorage.getItem(BOOT_CACHE_KEY);
    if (!raw) return null;
    const boot = JSON.parse(raw);
    if (!boot || !boot.ts || Date.now() - boot.ts > BOOT_CACHE_TTL_MS) {
      sessionStorage.removeItem(BOOT_CACHE_KEY);
      return null;
    }
    // One-shot for this navigation; keep until dashboard consumes year/measure match.
    return boot;
  } catch {
    return null;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('login-form');
  if (form) {
    if (sessionStorage.getItem('access_token')) {
      window.location.href = `/dashboard.html?farm=${getFarmId()}`;
      return;
    }
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const errEl = document.getElementById('login-error');
      errEl.classList.add('hidden');
      const btn = form.querySelector('button[type="submit"]');
      const setBusy = (label) => {
        if (btn) { btn.disabled = true; btn.textContent = label; }
      };
      setBusy('Signing in…');
      try {
        const data = await apiFetch('/auth/login', {
          method: 'POST',
          body: JSON.stringify({
            username: document.getElementById('username').value,
            password: document.getElementById('password').value,
          }),
        });
        setSession(data);
        const farm = data.user.farms[0]?.farm_id || 'KF';
        setBusy('Preparing dashboard…');
        try {
          await buildBootCache(data.access_token, farm);
        } catch (_) {
          /* dashboard will load cold */
        }
        window.location.href = `/dashboard.html?farm=${farm}`;
      } catch (err) {
        errEl.textContent = err.message || 'Invalid credentials';
        errEl.classList.remove('hidden');
        if (btn) { btn.disabled = false; btn.textContent = 'Sign In'; }
      }
    });
  }

  // Wake the serverless function as soon as the login page opens.
  const apiBase = typeof API_BASE !== 'undefined' ? API_BASE : '/api';
  const warmHealth = () => fetch(`${apiBase}/health`).catch(() => {});
  warmHealth();
  // Second ping shortly after — helps if the first request was a cold boot.
  setTimeout(warmHealth, 1500);
  const pwd = document.getElementById('password');
  const user = document.getElementById('username');
  const warmOnce = () => { warmHealth(); };
  pwd?.addEventListener('focus', warmOnce, { once: true });
  user?.addEventListener('input', warmOnce, { once: true });

  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) logoutBtn.addEventListener('click', logout);
});

window.getUser = getUser;
window.logout = logout;
window.requireAuth = requireAuth;
window.getFarmId = getFarmId;
window.takeBootCache = takeBootCache;
window.BOOT_CACHE_KEY = BOOT_CACHE_KEY;
