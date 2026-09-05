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
      if (btn) { btn.disabled = true; btn.textContent = 'Signing in…'; }
      try {
        const data = await apiFetch('/auth/login', {
          method: 'POST',
          body: JSON.stringify({
            username: document.getElementById('username').value,
            password: document.getElementById('password').value,
          }),
        });
        setSession(data);
        // Redirect immediately — do not block on dashboard data prefetch.
        const farm = data.user.farms[0]?.farm_id || 'KF';
        window.location.href = `/dashboard.html?farm=${farm}`;
      } catch (err) {
        errEl.textContent = err.message || 'Invalid credentials';
        errEl.classList.remove('hidden');
        if (btn) { btn.disabled = false; btn.textContent = 'Sign In'; }
      }
    });
  }

  // Wake serverless function while the user is on the login page.
  const apiBase = typeof API_BASE !== 'undefined' ? API_BASE : '/api';
  const warmHealth = () => fetch(`${apiBase}/health`).catch(() => {});
  warmHealth();
  setTimeout(warmHealth, 1200);
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
