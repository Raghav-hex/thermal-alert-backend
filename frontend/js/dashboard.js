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

// YOLOv5 model state
let ortSession = null;
let fireModelLoading = false;
let detectionsCache = {};
let lastInfTime = {};
let infQueue = [];
let infProcessing = false;
let pollTimerId = null;

async function loadFireModel() {
  if (ortSession) return ortSession;
  if (fireModelLoading) return null;
  fireModelLoading = true;
  try {
    ortSession = await ort.InferenceSession.create('/model/best.onnx');
    console.log('[MODEL] loaded (yolov5s-fire)');
    return ortSession;
  } catch (e) {
    console.warn('[MODEL] load failed:', e);
    return null;
  } finally {
    fireModelLoading = false;
  }
}

function preprocessFrame(ctx, ts) {
  const off = document.createElement('canvas');
  off.width = off.height = ts;
  const octx = off.getContext('2d');
  const s = Math.max(ts / ctx.canvas.width, ts / ctx.canvas.height);
  const dx = (ts - ctx.canvas.width * s) / 2;
  const dy = (ts - ctx.canvas.height * s) / 2;
  octx.drawImage(ctx.canvas, dx, dy, ctx.canvas.width * s, ctx.canvas.height * s);
  return octx.getImageData(0, 0, ts, ts);
}

async function detectWithModel(ctx) {
  const session = await loadFireModel();
  if (!session) return [];

  const imgData = preprocessFrame(ctx, 640);
  const N = 640 * 640;
  const input = new Float32Array(3 * N);
  for (let i = 0; i < N; i++) {
    input[i] = imgData.data[i * 4] / 255;
    input[N + i] = imgData.data[i * 4 + 1] / 255;
    input[2 * N + i] = imgData.data[i * 4 + 2] / 255;
  }

  const tensor = new ort.Tensor('float32', input, [1, 3, 640, 640]);
  const results = await session.run({ images: tensor });
  const data = results.output0.data;

  const boxes = [];
  for (let j = 0; j < 25200; j++) {
    const o = j * 6;
    const cx = data[o], cy = data[o + 1], w = data[o + 2], h = data[o + 3];
    const obj = data[o + 4];
    if (obj < 0.3) continue;
    boxes.push({
      x1: Math.max(0, cx - w/2), y1: Math.max(0, cy - h/2),
      x2: Math.min(640, cx + w/2), y2: Math.min(640, cy + h/2),
      conf: obj, cls: 0
    });
  }

  boxes.sort((a, b) => b.conf - a.conf);
  const keep = [];
  for (const box of boxes) {
    let overlap = false;
    for (const kept of keep) {
      const xi1 = Math.max(box.x1, kept.x1), yi1 = Math.max(box.y1, kept.y1);
      const xi2 = Math.min(box.x2, kept.x2), yi2 = Math.min(box.y2, kept.y2);
      const inter = Math.max(0, xi2 - xi1) * Math.max(0, yi2 - yi1);
      const union = (box.x2 - box.x1) * (box.y2 - box.y1) + (kept.x2 - kept.x1) * (kept.y2 - kept.y1) - inter;
      if (inter / union > 0.5) { overlap = true; break; }
    }
    if (!overlap) keep.push(box);
  }

  return keep;
}

async function loadDashboard() {
  if (!isLoggedIn()) { window.location.href = '/login.html'; return; }
  document.getElementById('username-display').textContent = localStorage.getItem('username');

  const modelPromise = loadFireModel().catch(() => null);

  try {
    [factories, stations] = await Promise.all([
      apiGet('/api/factories'),
      apiGet('/api/alerts/stations')
    ]);
    renderFactoryList();
    renderMap();
    loadActiveAlerts();
  } catch (e) {
    console.error('Failed to load data:', e);
  }

  await modelPromise;
  if (typeof window._hideLoading === 'function') window._hideLoading();
  setTimeout(() => map?.invalidateSize(), 300);
  initCameraGrid();

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
const POLL_MS = 50;
const RETRY_MS = 2000;
const MAX_STALE = 100;
let camGen = 0;
let frameFingerprint = {};
let frameStaleCount = {};

function getFingerprint(ctx, w, h) {
  const p1 = ctx.getImageData(15, 15, 1, 1).data;
  const p2 = ctx.getImageData(w >> 1, h >> 1, 1, 1).data;
  const p3 = ctx.getImageData(w - 15, h - 15, 1, 1).data;
  return p1[0]+','+p1[1]+','+p1[2]+'|'+
         p2[0]+','+p2[1]+','+p2[2]+'|'+
         p3[0]+','+p3[1]+','+p3[2];
}

function initCameraGrid() {
  const container = document.getElementById('camera-grid');
  container.innerHTML = '<div class="cam-grid"></div>';
  const grid = container.querySelector('.cam-grid');
  camGen++;
  const gen = camGen;

  for (let i = 1; i <= 8; i++) {
    const card = document.createElement('div');
    card.className = 'cam-card';
    card.dataset.fid = i;
    card.innerHTML = `
      <canvas width="640" height="480" style="width:100%;aspect-ratio:4/3;display:block;background:#0a121a;" id="cam-canvas-${i}"></canvas>
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
    schedulePoll(i, gen, true);
  }
}

function schedulePoll(idx, gen, immediate, isRetry) {
  if (gen !== camGen) return;
  if (!localStorage.getItem('token')) return;
  if (document.getElementById('camera-grid').style.display === 'none') {
    setTimeout(() => schedulePoll(idx, gen, true, isRetry), RETRY_MS);
    return;
  }
  const delay = isRetry ? RETRY_MS : immediate ? 0 : POLL_MS;
  setTimeout(() => pollOne(idx, gen), delay);
}

function pollOne(idx, gen) {
  if (gen !== camGen) return;

  const img = new Image();
  img.crossOrigin = 'anonymous';

  img.onload = function() {
    if (gen !== camGen) return;
    const canvas = document.getElementById('cam-canvas-' + idx);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (canvas.width !== img.width) canvas.width = img.width;
    if (canvas.height !== img.height) canvas.height = img.height;
    ctx.drawImage(img, 0, 0);

    const fp = getFingerprint(ctx, canvas.width, canvas.height);
    if (fp === frameFingerprint[idx]) {
      frameStaleCount[idx] = (frameStaleCount[idx] || 0) + 1;
    } else {
      frameStaleCount[idx] = 0;
      frameFingerprint[idx] = fp;
    }

    if (frameStaleCount[idx] > MAX_STALE) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const ov = document.getElementById('cam-overlay-' + idx);
      if (ov) ov.style.display = '';
      const dt = document.getElementById('cam-dot-' + idx);
      if (dt) dt.className = 'cam-dot offline';
      schedulePoll(idx, gen, false, true);
      return;
    }

    const dets = detectionsCache[idx] || [];
    const sx = canvas.width / 640;
    const sy = canvas.height / 640;

    if (dets.length > 0) {
      const best = dets.reduce((a, b) => a.conf > b.conf ? a : b);
      ctx.font = 'bold 26px monospace';
      ctx.textBaseline = 'top';
      ctx.fillStyle = '#ff4500';
      ctx.strokeStyle = '#000';
      ctx.lineWidth = 4;
      ctx.strokeText('FIRE ' + Math.round(best.conf * 100) + '%', 12, 12);
      ctx.fillText('FIRE ' + Math.round(best.conf * 100) + '%', 12, 12);
      ctx.strokeStyle = '#ff4500';
      ctx.lineWidth = 3;
      for (const d of dets) {
        ctx.strokeRect(d.x1 * sx, d.y1 * sy, (d.x2 - d.x1) * sx, (d.y2 - d.y1) * sy);
      }
    }

    const ov = document.getElementById('cam-overlay-' + idx);
    if (ov) ov.style.display = 'none';
    const dt = document.getElementById('cam-dot-' + idx);
    if (dt) dt.className = 'cam-dot live';

    triggerNextInference();
    schedulePoll(idx, gen);
  };

  img.onerror = function() {
    if (gen !== camGen) return;
    const canvas = document.getElementById('cam-canvas-' + idx);
    if (canvas) {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    const ov = document.getElementById('cam-overlay-' + idx);
    if (ov) ov.style.display = '';
    const dt = document.getElementById('cam-dot-' + idx);
    if (dt) dt.className = 'cam-dot offline';

    schedulePoll(idx, gen, false, true);
  };

  img.src = API_CAM + '/api/camera/latest/' + idx + '?t=' + Date.now();
}

// Inference queue — one at a time
let infRoundRobin = 1;

function enqueueInference(idx) {
  if (infQueue.indexOf(idx) !== -1) return;
  if (infQueue.length >= 4) return;
  infQueue.push(idx);
  processInfQueue();
}

async function processInfQueue() {
  if (infProcessing) return;
  infProcessing = true;
  while (infQueue.length > 0) {
    const idx = infQueue.shift();
    await new Promise(r => setTimeout(r, 0));
    const canvas = document.getElementById('cam-canvas-' + idx);
    if (!canvas) continue;
    const ctx = canvas.getContext('2d');
    try {
      const dets = await detectWithModel(ctx);
      detectionsCache[idx] = dets;
      if (dets.length > 0) {
        console.log('[FIRE ' + idx + '] ' + Math.round(dets[0].conf * 100) + '%');
      }
    } catch (e) {
      console.warn('[FIRE ' + idx + '] err:', e);
    }
  }
  infProcessing = false;
}

function triggerNextInference() {
  const now = Date.now();
  for (let attempt = 0; attempt < 8; attempt++) {
    const idx = infRoundRobin;
    infRoundRobin = (infRoundRobin % 8) + 1;
    const canvas = document.getElementById('cam-canvas-' + idx);
    if (!canvas) continue;
    const dot = document.getElementById('cam-dot-' + idx);
    if (!dot || dot.className.indexOf('live') === -1) continue;
    if (lastInfTime[idx] && now - lastInfTime[idx] < 5000) continue;
    lastInfTime[idx] = now;
    enqueueInference(idx);
    return;
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
    container.innerHTML = '<h3 style="display:inline">Active Alerts</h3> <button id="resolve-all-btn" style="float:right;padding:2px 10px;background:#e63946;color:#fff;border:none;border-radius:4px;font-size:11px;cursor:pointer;">Resolve All</button><div style="clear:both"></div>';
    const rbtn = document.getElementById('resolve-all-btn');
    if (rbtn) rbtn.onclick = resolveAllAlerts;

    if (!alerts || alerts.length === 0) {
      const rem = document.getElementById('resolve-all-btn');
      if (rem) rem.remove();
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

async function resolveAllAlerts() {
  try {
    await apiPost('/api/alerts/resolve-all', {});
    clearRoutes();
    loadActiveAlerts();
  } catch (e) {
    console.error('Failed to resolve all:', e);
  }
}
