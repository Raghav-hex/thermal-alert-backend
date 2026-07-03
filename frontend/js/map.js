let map;
let factoryMarkers = [];
let stationMarkers = [];
let routeLayer = null;
let alertCircle = null;

const TNGIS_WMS = 'https://tngis.tn.gov.in/geoserver/wms';

const STATION_ICONS = {
  hospital: L.divIcon({
    html: '<div style="background:#e63946;color:#fff;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:bold;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.4);">H</div>',
    className: '', iconSize: [30, 30], iconAnchor: [15, 15]
  }),
  fire_station: L.divIcon({
    html: '<div style="background:#ff6b35;color:#fff;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:bold;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.4);">F</div>',
    className: '', iconSize: [30, 30], iconAnchor: [15, 15]
  }),
  police: L.divIcon({
    html: '<div style="background:#4361ee;color:#fff;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:bold;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.4);">P</div>',
    className: '', iconSize: [30, 30], iconAnchor: [15, 15]
  })
};

function initMap(center = [9.4535, 77.8067], zoom = 14) {
  map = L.map('map', {
    center, zoom,
    zoomControl: true,
    attributionControl: true
  });

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://openstreetmap.org">OSM</a>'
  }).addTo(map);

  L.tileLayer.wms(TNGIS_WMS, {
    layers: 'tngis:road_network',
    format: 'image/png',
    transparent: true,
    opacity: 0.5,
    attribution: '&copy; TNGIS'
  }).addTo(map);

  const legend = L.control({ position: 'bottomright' });
  legend.onAdd = function () {
    const div = L.DomUtil.create('div', 'map-legend');
    div.innerHTML = `
      <div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ff4444;margin-right:6px;"></span> Factory (High Risk)</div>
      <div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#fbbf24;margin-right:6px;"></span> Factory (Medium Risk)</div>
      <div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#4ade80;margin-right:6px;"></span> Factory (Low Risk)</div>
      <div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#e63946;margin-right:6px;"></span> H - Hospital</div>
      <div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ff6b35;margin-right:6px;"></span> F - Fire Station</div>
      <div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#4361ee;margin-right:6px;"></span> P - Police Station</div>
    `;
    return div;
  };
  legend.addTo(map);
}

function addFactoryMarker(factory, onClick) {
  const colors = { high: '#ff4444', medium: '#fbbf24', low: '#4ade80' };
  const color = colors[factory.risk] || '#4ade80';
  const icon = L.divIcon({
    html: `<div style="background:${color};color:#fff;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:bold;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.5);cursor:pointer;">${factory.id}</div>`,
    className: '', iconSize: [30, 30], iconAnchor: [15, 15]
  });

  const marker = L.marker([factory.lat, factory.lon], { icon })
    .addTo(map)
    .bindPopup(`<b>${factory.name}</b><br>Risk: ${factory.risk}`);

  if (onClick) marker.on('click', () => onClick(factory));
  factoryMarkers.push(marker);
  return marker;
}

function addStationMarker(station) {
  const icon = STATION_ICONS[station.type] || STATION_ICONS.hospital;
  const marker = L.marker([station.lat, station.lon], { icon })
    .addTo(map)
    .bindPopup(`<b>${station.name}</b><br>Type: ${station.type}`);
  stationMarkers.push(marker);
  return marker;
}

function addAlertMarker(lat, lon, label) {
  if (alertCircle) map.removeLayer(alertCircle);
  alertCircle = L.circle([lat, lon], {
    radius: 300, color: '#ff4444', fillColor: '#ff4444',
    fillOpacity: 0.15, weight: 2, dashArray: '5,5'
  }).addTo(map);

  const alertIcon = L.divIcon({
    html: '<div style="background:#ff4444;color:#fff;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:bold;border:2px solid #fff;box-shadow:0 0 20px rgba(255,68,68,0.8);animation:pulse-marker 1s infinite;">!</div>',
    className: '', iconSize: [36, 36], iconAnchor: [18, 18]
  });
  const marker = L.marker([lat, lon], { icon: alertIcon }).addTo(map);
  marker.bindPopup(`<b> ALERT</b><br>${label}`);
  map.setView([lat, lon], 14);
}

function drawRoute(geometry) {
  if (routeLayer) map.removeLayer(routeLayer);
  if (!geometry) return;
  routeLayer = L.geoJSON(geometry, {
    style: { color: '#ff6b35', weight: 4, opacity: 0.8 }
  }).addTo(map);
  map.fitBounds(routeLayer.getBounds(), { padding: [50, 50] });
}

function clearRoutes() {
  if (routeLayer) { map.removeLayer(routeLayer); routeLayer = null; }
  if (alertCircle) { map.removeLayer(alertCircle); alertCircle = null; }
}

function clearStationMarkers() {
  stationMarkers.forEach(m => map.removeLayer(m));
  stationMarkers = [];
}

function clearFactoryMarkers() {
  factoryMarkers.forEach(m => map.removeLayer(m));
  factoryMarkers = [];
}
