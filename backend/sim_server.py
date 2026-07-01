import os, sys
import random, httpx, threading
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))
from config import FACTORY_DATA, WARNING_THRESHOLD_TEMP, CRITICAL_THRESHOLD_TEMP, WARNING_THRESHOLD_SMOKE, CRITICAL_THRESHOLD_SMOKE, WARNING_THRESHOLD_HUMIDITY_LOW, WARNING_THRESHOLD_HUMIDITY_HIGH, WARNING_THRESHOLD_PRESSURE, CRITICAL_THRESHOLD_PRESSURE

MAIN_SERVER_URL = os.environ.get("MAIN_SERVER_URL", "http://localhost:8000")

app = FastAPI(title="Thermal Alert - Simulation Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sim_state = {}
auto_mode = False
factory_critical_already_sent = set()


def _init_factory_state(factory):
    fid = factory["id"]
    if fid not in sim_state:
        base = factory["base_temp"]
        sim_state[fid] = {
            "temperature": round(base + random.uniform(-2, 2), 1),
            "humidity": round(random.uniform(40, 60), 1),
            "smoke_level": round(random.uniform(2, 15), 1),
            "pressure": round(random.uniform(0.98, 1.12), 2),
            "status": "normal",
        }
    return sim_state[fid]


def _evaluate_status(state):
    t = state["temperature"]
    s = state["smoke_level"]
    h = state["humidity"]
    p = state["pressure"]

    if t >= CRITICAL_THRESHOLD_TEMP or s >= CRITICAL_THRESHOLD_SMOKE or p >= CRITICAL_THRESHOLD_PRESSURE:
        return "critical"
    if t >= WARNING_THRESHOLD_TEMP or s >= WARNING_THRESHOLD_SMOKE or h >= WARNING_THRESHOLD_HUMIDITY_HIGH or h <= WARNING_THRESHOLD_HUMIDITY_LOW or p >= WARNING_THRESHOLD_PRESSURE:
        return "warning"
    return "normal"


def _safe_step(current, base, max_deviation=6, step=3):
    drift = random.uniform(-step, step)
    new_val = current + drift
    lower = base - max_deviation
    upper = base + max_deviation
    if new_val < lower:
        new_val = lower + abs(drift) * 0.3
    if new_val > upper:
        new_val = upper - abs(drift) * 0.3
    return round(max(20, min(120, new_val)), 1)


class UpdateSensorRequest(BaseModel):
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    smoke_level: Optional[float] = None
    pressure: Optional[float] = None


def _send_alert_async(factory_id: int, factory_name: str, lat: float, lon: float, temp: float, smoke: float):
    def do_send():
        try:
            payload = {
                "factory_id": factory_id,
                "factory_name": factory_name,
                "lat": lat,
                "lon": lon,
                "temperature": temp,
                "smoke_level": smoke,
                "triggered_by": "simulation",
            }
            with httpx.Client(timeout=20) as client:
                resp = client.post(f"{MAIN_SERVER_URL}/api/alerts/trigger", json=payload)
                if resp.status_code == 200:
                    print(f"Alert sent to main server for {factory_name}")
                else:
                    print(f"Alert send failed (status {resp.status_code})")
        except Exception as e:
            print(f"Alert send error: {e}")
    t = threading.Thread(target=do_send, daemon=True)
    t.start()


@app.get("/api/simulation/state")
def get_simulation_state():
    for factory in FACTORY_DATA:
        _init_factory_state(factory)
        state = sim_state[factory["id"]]
        state["status"] = _evaluate_status(state)

    result = []
    for factory in FACTORY_DATA:
        state = sim_state.get(factory["id"], {})
        result.append({
            "id": factory["id"],
            "name": factory["name"],
            "lat": factory["lat"],
            "lon": factory["lon"],
            "risk": factory["risk"],
            "base_temp": factory["base_temp"],
            "status": state.get("status", "normal"),
            "alert_sent": factory["id"] in factory_critical_already_sent,
            "sensors": {
                "temperature": state.get("temperature", 0),
                "humidity": state.get("humidity", 0),
                "smoke_level": state.get("smoke_level", 0),
                "pressure": state.get("pressure", 0),
            },
        })
    return {"factories": result, "auto_mode": auto_mode}


@app.post("/api/simulation/update/{factory_id}")
async def update_sensor(factory_id: int, req: UpdateSensorRequest):
    factory = next((f for f in FACTORY_DATA if f["id"] == factory_id), None)
    if not factory:
        raise HTTPException(status_code=404, detail="Factory not found")

    _init_factory_state(factory)
    state = sim_state[factory_id]
    if req.temperature is not None:
        state["temperature"] = round(req.temperature, 1)
    if req.humidity is not None:
        state["humidity"] = round(req.humidity, 1)
    if req.smoke_level is not None:
        state["smoke_level"] = round(req.smoke_level, 1)
    if req.pressure is not None:
        state["pressure"] = round(req.pressure, 1)

    old_status = state.get("status", "normal")
    state["status"] = _evaluate_status(state)

    if state["status"] == "critical" and old_status != "critical":
        _send_alert_async(
            factory_id, factory["name"], factory["lat"], factory["lon"],
            state["temperature"], state["smoke_level"],
        )

    return {"message": "Updated", "factory_id": factory_id, "status": state["status"]}


@app.post("/api/simulation/tick")
async def auto_tick():
    for factory in FACTORY_DATA:
        _init_factory_state(factory)
        state = sim_state[factory["id"]]
        base = factory["base_temp"]
        state["temperature"] = _safe_step(state["temperature"], base, max_deviation=8, step=4)
        state["smoke_level"] = _safe_step(state["smoke_level"], 8, max_deviation=35, step=8)
        state["humidity"] = _safe_step(state["humidity"], 50, max_deviation=18, step=5)
        state["pressure"] = _safe_step(state["pressure"], 1.05, max_deviation=0.35, step=0.05)

        old_status = state.get("status", "normal")
        state["status"] = _evaluate_status(state)

        if state["status"] == "critical" and old_status != "critical":
            _send_alert_async(
                factory["id"], factory["name"], factory["lat"], factory["lon"],
                state["temperature"], state["smoke_level"],
            )

    return get_simulation_state()


@app.post("/api/simulation/auto")
def toggle_auto(mode: bool):
    global auto_mode
    auto_mode = mode
    return {"auto_mode": auto_mode}


FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend", "sim_standalone")


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    filepath = os.path.join(FRONTEND, full_path) if full_path else os.path.join(FRONTEND, "index.html")
    if not full_path:
        filepath = os.path.join(FRONTEND, "index.html")
    if os.path.isfile(filepath):
        return FileResponse(filepath)
    filepath = os.path.join(FRONTEND, "index.html")
    if os.path.isfile(filepath):
        return FileResponse(filepath)
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
