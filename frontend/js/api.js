// Local dev: same-origin on :8000, or frontend :3000 → API :8000
function resolveApiBase() {
  if (window.API_URL) return window.API_URL;
  const host = window.location.hostname;
  const port = window.location.port;
  const isLocal = host === 'localhost' || host === '127.0.0.1' || host === '[::1]';
  if (isLocal && port === '8000') return '/api';
  if (isLocal && port && port !== '8000') {
    const apiHost = host === '[::1]' ? 'localhost' : host;
    return `http://${apiHost}:8000/api`;
  }
  return '/api';
}
const API_BASE = resolveApiBase();

async function apiFetch(path, options = {}) {
  const token = sessionStorage.getItem('access_token');
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error(
      'Cannot reach the API. Run: cd backend && uvicorn app.main:app --reload --port 8000 then open http://localhost:8000/login.html'
    );
  }
  if (res.status === 401) {
    sessionStorage.removeItem('access_token');
    if (!window.location.pathname.includes('login')) {
      window.location.href = '/login.html';
    }
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return res.json();
  return res;
}

async function apiDownload(path, filename) {
  const token = sessionStorage.getItem('access_token');
  const res = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error('Download failed');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function apiPostDownload(path, body, filename) {
  const token = sessionStorage.getItem('access_token');
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Download failed');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

window.apiFetch = apiFetch;
window.apiDownload = apiDownload;
window.apiPostDownload = apiPostDownload;
