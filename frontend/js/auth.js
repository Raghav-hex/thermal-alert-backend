const API = (typeof API_BASE_URL !== 'undefined') ? API_BASE_URL : window.location.origin;

async function login(username, password) {
  const res = await fetch(`${API}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  });
  if (!res.ok) throw new Error('Invalid credentials');
  const data = await res.json();
  localStorage.setItem('token', data.access_token);
  localStorage.setItem('username', data.username);
  localStorage.setItem('is_admin', data.is_admin);
  localStorage.setItem('role', data.role || (data.is_admin ? 'admin' : 'factory'));
  localStorage.setItem('factory_id', data.factory_id || '');
  return data;
}

async function register(username, email, password) {
  const res = await fetch(`${API}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password })
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Registration failed');
  }
  return await res.json();
}

function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('username');
  localStorage.removeItem('is_admin');
  window.location.href = '/login.html';
}

function getToken() {
  return localStorage.getItem('token');
}

function isLoggedIn() {
  return !!getToken();
}

async function apiGet(path) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, { headers });
  if (res.status === 401) { logout(); throw new Error('Unauthorized'); }
  return await res.json();
}

async function apiPost(path, body) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body)
  });
  if (res.status === 401) { logout(); throw new Error('Unauthorized'); }
  return await res.json();
}
