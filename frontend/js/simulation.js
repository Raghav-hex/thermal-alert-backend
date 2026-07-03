let simFactories = [];
let autoMode = false;
let autoInterval = null;

async function loadSimulation() {
  if (!isLoggedIn()) { window.location.href = '/login.html'; return; }
  document.getElementById('username-display').textContent = localStorage.getItem('username');

  document.getElementById('btn-manual').addEventListener('click', () => setMode('manual'));
  document.getElementById('btn-auto').addEventListener('click', () => setMode('auto'));
  document.getElementById('btn-reset').addEventListener('click', resetAll);

  document.getElementById('nav-dashboard').addEventListener('click', goToDashboard);
  document.getElementById('nav-simulation').addEventListener('click', () => {});

  await refreshSimState();
}

async function refreshSimState() {
  try {
    const data = await apiGet('/api/simulation/state');
    simFactories = data.factories || [];
    autoMode = data.auto_mode || false;
    updateModeUI();
    renderSimCards();
  } catch (e) {
    console.error('Failed to load simulation state:', e);
  }
}

function renderSimCards() {
  const container = document.getElementById('sensor-cards');
  container.innerHTML = '';

  simFactories.forEach(f => {
    const card = document.createElement('div');
    card.className = 'sensor-card';
    const riskColor = { high: '#ff4444', medium: '#fbbf24', low: '#4ade80' };
    const statusColor = { critical: '#ff4444', warning: '#fbbf24', normal: '#4ade80' };

    card.innerHTML = `
      <div class="factory-header">
        <div>
          <div class="factory-name"> ${f.name}</div>
          <span class="factory-risk" style="background:${riskColor[f.risk] || '#4ade80'};color:#000;padding:2px 8px;border-radius:10px;font-size:11px;">${f.risk.toUpperCase()}</span>
          <span class="status-badge ${f.status}" style="margin-left:6px;">${f.status.toUpperCase()}</span>
        </div>
        <button class="btn-danger" style="padding:6px 14px;border:none;border-radius:6px;font-size:12px;cursor:pointer;" onclick="triggerAlert(${f.id})"> Trigger Alert</button>
      </div>
      <div class="sensor-grid">
        <div class="sensor-item">
          <div class="label"> Temperature</div>
          <div class="value" style="color:${f.sensors.temperature >= 70 ? '#ff4444' : f.sensors.temperature >= 45 ? '#fbbf24' : '#4ade80'}">${f.sensors.temperature} °C</div>
          <div class="slider-container">
            <input type="range" min="20" max="120" value="${f.sensors.temperature}"
              oninput="updateSensor(${f.id}, 'temperature', this.value)"
              ${autoMode ? 'disabled' : ''}>
          </div>
        </div>
        <div class="sensor-item">
          <div class="label"> Humidity</div>
          <div class="value" style="color:${f.sensors.humidity >= 80 || f.sensors.humidity <= 20 ? '#fbbf24' : '#4ade80'}">${f.sensors.humidity} %</div>
          <div class="slider-container">
            <input type="range" min="0" max="100" value="${f.sensors.humidity}"
              oninput="updateSensor(${f.id}, 'humidity', this.value)"
              ${autoMode ? 'disabled' : ''}>
          </div>
        </div>
        <div class="sensor-item">
          <div class="label"> Smoke Level</div>
          <div class="value" style="color:${f.sensors.smoke_level >= 80 ? '#ff4444' : f.sensors.smoke_level >= 50 ? '#fbbf24' : '#4ade80'}">${f.sensors.smoke_level} %</div>
          <div class="slider-container">
            <input type="range" min="0" max="100" value="${f.sensors.smoke_level}"
              oninput="updateSensor(${f.id}, 'smoke_level', this.value)"
              ${autoMode ? 'disabled' : ''}>
          </div>
        </div>
        <div class="sensor-item">
          <div class="label"> Pressure</div>
          <div class="value" style="color:${f.sensors.pressure >= 1.8 ? '#ff4444' : f.sensors.pressure >= 1.5 ? '#fbbf24' : '#4ade80'}">${f.sensors.pressure} atm</div>
          <div class="slider-container">
            <input type="range" min="0.8" max="2.0" step="0.01" value="${f.sensors.pressure}"
              oninput="updateSensor(${f.id}, 'pressure', this.value)"
              ${autoMode ? 'disabled' : ''}>
          </div>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

async function updateSensor(factoryId, sensor, value) {
  if (autoMode) return;
  const body = { [sensor]: parseFloat(value) };
  try {
    await apiPost(`/api/simulation/update/${factoryId}`, body);
    await refreshSimState();
  } catch (e) {
    console.error('Update failed:', e);
  }
}

async function setMode(mode) {
  if (mode === 'auto') {
    autoMode = !autoMode;
    await apiPost('/api/simulation/auto', { mode: autoMode });
    if (autoMode) {
      startAutoTick();
    } else {
      stopAutoTick();
    }
  } else {
    stopAutoTick();
    autoMode = false;
    await apiPost('/api/simulation/auto', { mode: false });
  }
  updateModeUI();
  if (!autoMode) await refreshSimState();
}

function startAutoTick() {
  stopAutoTick();
  autoInterval = setInterval(async () => {
    try {
      const data = await apiPost('/api/simulation/tick', {});
      simFactories = data.factories || [];
      renderSimCards();
      checkForAutoAlerts(data.factories || []);
    } catch (e) {
      console.error('Auto tick failed:', e);
    }
  }, 30000);
}

function stopAutoTick() {
  if (autoInterval) { clearInterval(autoInterval); autoInterval = null; }
}

function checkForAutoAlerts(factories) {
  const critical = factories.filter(f => f.status === 'critical');
  critical.forEach(f => {
    showNotification(` CRITICAL: ${f.name} — Temperature ${f.sensors.temperature}°C`);
  });
}

function showNotification(msg) {
  const el = document.createElement('div');
  el.style.cssText = `
    position:fixed;top:20px;right:20px;background:#4a1a1a;color:#ff4444;
    padding:16px 20px;border-radius:8px;border:1px solid #ff4444;
    font-weight:600;z-index:9999;max-width:400px;
    box-shadow:0 4px 20px rgba(0,0,0,0.5);
    animation: slideIn 0.3s ease;
  `;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

async function triggerAlert(factoryId) {
  try {
    const result = await apiPost(`/api/simulation/trigger/${factoryId}`, {});
    showNotification(` Alert #${result.alert_id} triggered for factory ${factoryId}`);
  } catch (e) {
    console.error('Trigger failed:', e);
  }
}

async function resetAll() {
  stopAutoTick();
  autoMode = false;
  await apiPost('/api/simulation/auto', { mode: false });
  for (const f of simFactories) {
    await apiPost(`/api/simulation/update/${f.id}`, {
      temperature: f.base_temp || 30,
      humidity: 45,
      smoke_level: 15,
      pressure: 1.01
    });
  }
  await refreshSimState();
}

function updateModeUI() {
  const btnManual = document.getElementById('btn-manual');
  const btnAuto = document.getElementById('btn-auto');
  btnManual.classList.toggle('active', !autoMode);
  btnAuto.classList.toggle('active', autoMode);
  btnAuto.textContent = autoMode ? '⏹ Stop Auto (30s)' : ' Auto Mode (30s)';
  renderSimCards();
}

function goToDashboard() {
  window.location.href = '/';
}

document.addEventListener('visibilitychange', () => {
  if (document.hidden && autoMode) stopAutoTick();
  if (!document.hidden && autoMode) startAutoTick();
});
