import os

DATABASE_URL = "sqlite:///./thermal_alert.db"
SECRET_KEY = "sivakasi-thermal-alert-secret-key-2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

SIVAKASI_CENTER = {"lat": 9.4535, "lon": 77.8067}
SIVAKASI_BBOX = {"lat1": 9.30, "lon1": 77.65, "lat2": 9.60, "lon2": 77.95}
ALERT_RADIUS_KM = 10.0

OSRM_BASE_URL = "https://router.project-osrm.org"

TNGIS_WMS_URL = "https://tngis.tn.gov.in/geoserver/wms"
TNGIS_ROADS_LAYER = "tngis:road_network"

WARNING_THRESHOLD_TEMP = 45.0
CRITICAL_THRESHOLD_TEMP = 70.0
WARNING_THRESHOLD_SMOKE = 50.0
CRITICAL_THRESHOLD_SMOKE = 80.0
WARNING_THRESHOLD_HUMIDITY_LOW = 20.0
WARNING_THRESHOLD_HUMIDITY_HIGH = 80.0
WARNING_THRESHOLD_PRESSURE = 1.5
CRITICAL_THRESHOLD_PRESSURE = 1.8

FACTORY_DATA = [
    {"id": 1, "name": "Sri Kaliswari Fireworks", "lat": 9.4430, "lon": 77.7950, "risk": "medium", "base_temp": 32.0},
    {"id": 2, "name": "Standard Fireworks", "lat": 9.4480, "lon": 77.8100, "risk": "low", "base_temp": 28.0},
    {"id": 3, "name": "Ayyan Fireworks", "lat": 9.4380, "lon": 77.8020, "risk": "medium", "base_temp": 36.0},
    {"id": 4, "name": "Raja Fireworks", "lat": 9.4580, "lon": 77.8000, "risk": "low", "base_temp": 30.0},
    {"id": 5, "name": "Sakthi Fireworks", "lat": 9.4630, "lon": 77.8150, "risk": "medium", "base_temp": 33.0},
    {"id": 6, "name": "Muthu Fireworks", "lat": 9.4330, "lon": 77.7900, "risk": "medium", "base_temp": 34.0},
    {"id": 7, "name": "Pandian Fireworks", "lat": 9.4530, "lon": 77.8200, "risk": "low", "base_temp": 32.0},
    {"id": 8, "name": "Sivakasi Fireworks Industries", "lat": 9.4480, "lon": 77.7850, "risk": "low", "base_temp": 29.0},
]
