let factories = [];
let stations = [];
let activeAlert = null;
let factoryNames = {
  1: 'Sri Kaliswari Fireworks',
  2: 'Standard Fireworks',
  3: 'Ayyan Fireworks',
  4: 'Raja Fireworks',
  5: 'Sakthi Fireworks',
  6: 'Muthu Fireworks',
  7: 'Pandian Fireworks',
  8: 'Sivakasi Fireworks Industries',
};

async function loadDashboard() {
  if (!isLoggedIn()) { window.location.href = '/login.html'; return; }
  document.getElementById('username-display').textContent = localStorage.getItem('username');

  try {
    factories = await apiGet('/api/factories');
    stations = await apiGet('/api/alerts/stations');
    renderFactoryList();
    renderMap();
    loadActiveAlerts();
    initCameraGrid();
  } catch (e) {
    console.error('Failed to load data:', e);
  }

  document.getElementById('nav-dashboard').addEventListener('click', () => {
    document.getElementById('nav-dashboard').classList.add('active');
    document.getElementById('nav-cameras').classList.remove('active');
    document.getElementById('map').style.display = 'block';
    document.getElementById('camera-grid').style.display = 'none';
    setTimeout(() => map?.invalidateSize(), 100);
  });

  document.getElementById('nav-cameras').addEventListener('click', () => {
    document.getElementById('nav-cameras').classList.add('active');
    document.getElementById('nav-dashboard').classList.remove('active');
    document.getElementById('map').style.display = 'none';
    document.getElementById('camera-grid').style.display = 'block';
    initCameraGrid();
  });
}

const API_CAM = 'https://thermal-alert-backend.onrender.com';

function initCameraGrid() {
  const container = document.getElementById('camera-grid');
  container.innerHTML = '<div class="cam-grid"></div>';
  const grid = container.querySelector('.cam-grid');

  for (let i = 1; i <= 8; i++) {
    const card = document.createElement('div');
    card.className = 'cam-card';
    card.dataset.fid = i;
    card.innerHTML = `
      <img style="width:100%;aspect-ratio:4/3;object-fit:cover;display:block;background:#0a121a;" id="cam-img-${i}" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" onload="document.getElementById('cam-overlay-${i}').style.display='none';document.getElementById('cam-dot-${i}').className='cam-dot live';" onerror="document.getElementById('cam-overlay-${i}').style.display='flex';document.getElementById('cam-dot-${i}').className='cam-dot offline';">
      <div class="cam-overlay" id="cam-overlay-${i}">No signal</div>
      <button class="cam-close" onclick="closeExpanded()">x</button>
      <div class="cam-label">
        <span class="cam-name">${factoryNames[i]}</span>
        <div>
          <span class="cam-dot offline" id="cam-dot-${i}"></span>
        </div>
      </div>
    `;
    card.addEventListener('click', function(e) {
      if (e.target.closest('.cam-close')) return;
      if (!this.classList.contains('expanded')) expandCam(i);
    });
    grid.appendChild(card);
  }

  pollCameraFrames();
}

function pollCameraFrames() {
  const token = localStorage.getItem('token');
  if (!token) return;

  for (let i = 1; i <= 8; i++) {
    const gt = document.getElementById('cam-overlay-' + i);
    if (gt) gt.style.display = 'flex';
    const dt = document.getElementById('cam-dot-' + i);
    if (dt) dt.className = 'cam-dot offline';
    const img = document.getElementById('cam-img-' + i);
    if (img) {
      img.src = API_CAM + '/api/camera/latest/' + i + '?t=' + Date.now();
    }
  }

  if (document.getElementById('camera-grid').style.display !== 'none') {
    setTimeout(pollCameraFrames, 100);
  }
}

function expandCam(factoryId) {
  const cards = document.querySelectorAll('.cam-card');
  cards.forEach(c => c.classList.remove('expanded'));

  const card = document.querySelector(`.cam-card[data-fid="${factoryId}"]`);
  if (card) card.classList.add('expanded');
}

function closeExpanded() {
  document.querySelectorAll('.cam-card').forEach(c => c.classList.remove('expanded'));
}

function renderMap() {
  initMap();

  factories.forEach(f => {
    addFactoryMarker(f, (factory) => {
      document.querySelector(`[data-fid="${factory.id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  });

  if (stations && stations.length) {
    stations.forEach(s => addStationMarker(s));
  }

  new ResizeObserver(() => map.invalidateSize()).observe(document.getElementById('map'));
}

function renderFactoryList() {
  const container = document.getElementById('factory-list');
    container.innerHTML = '<h3 style="font-size:13px;color:#8899aa;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px;">FACTORIES</h3>';

  factories.forEach(f => {
    const div = document.createElement('div');
    div.className = `factory-item risk-${f.risk}`;
    div.dataset.fid = f.id;
    const status = f.status || 'normal';
    div.innerHTML = `
      <div class="name">${f.name}</div>
      <div class="meta">Risk: ${f.risk} | ${f.lat.toFixed(4)}, ${f.lon.toFixed(4)}</div>
      <span class="status-badge ${status}">${status.toUpperCase()}</span>
    `;
    div.addEventListener('click', () => {
      map.setView([f.lat, f.lon], 15);
      factoryMarkers[f.id - 1]?.openPopup();
    });
    container.appendChild(div);
  });
}

async function loadActiveAlerts() {
  try {
    const alerts = await apiGet('/api/alerts/active');
    const container = document.getElementById('alert-list');
    container.innerHTML = '<h3>Active Alerts</h3>';

    if (!alerts || alerts.length === 0) {
      container.innerHTML += '<p style="color:#4ade80;font-size:13px;padding:8px 0;">All Clear - No active alerts</p>';
      return;
    }

    alerts.forEach(a => {
      activeAlert = a;
      addAlertMarker(a.lat, a.lon, a.factory_name);

      const card = document.createElement('div');
      card.className = 'alert-card';
      card.innerHTML = `
        <div class="alert-title">ALERT: ${a.factory_name}</div>
        <div class="alert-meta">Temp: ${a.temperature}°C | Smoke: ${a.smoke_level}% | ${new Date(a.created_at).toLocaleTimeString()}</div>
        <div class="alert-stations">
          ${a.notifications.map(n => `
            <div class="station-item">
              <div>
                <span class="sicon" style="display:inline-block;width:18px;height:18px;border-radius:50%;color:#fff;font-size:10px;font-weight:bold;text-align:center;line-height:18px;${n.station_type === 'hospital' ? 'background:#e63946' : n.station_type === 'fire_station' ? 'background:#ff6b35' : 'background:#4361ee'}">${n.station_type === 'hospital' ? 'H' : n.station_type === 'fire_station' ? 'F' : 'P'}</span>
                <span class="sname">${n.station_name}</span>
                <span class="sdist">${n.distance_km} km${n.eta_min ? ` · ${n.eta_min} min` : ''}</span>
              </div>
              <button class="route-btn" onclick="showRoute(${a.id}, '${n.station_id}')">Route</button>
            </div>
          `).join('')}
        </div>
        <button onclick="resolveAlert(${a.id})" style="margin-top:8px;padding:4px 12px;background:#2a3a4a;color:#8899aa;border:none;border-radius:4px;font-size:11px;cursor:pointer;">Resolve</button>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    console.error('Failed to load alerts:', e);
  }
}

async function showRoute(alertId, stationId) {
  try {
    const route = await apiGet(`/api/alerts/${alertId}/route/${stationId}`);
    if (route && route.geometry) {
      drawRoute(route.geometry);
      const station = stations.find(s => s.id === stationId);
      if (station) {
        L.popup()
          .setLatLng([station.lat, station.lon])
          .setContent(`<b>${station.name}</b><br>ETA: ${route.duration_min} min (${route.distance_km} km)`)
          .openOn(map);
      }
    }
  } catch (e) {
    console.error('Route failed:', e);
  }
}

async function resolveAlert(alertId) {
  try {
    await apiPost(`/api/alerts/resolve/${alertId}`, {});
    clearRoutes();
    loadActiveAlerts();
  } catch (e) {
    console.error('Failed to resolve:', e);
  }
}
