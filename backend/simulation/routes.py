from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import random

from config import FACTORY_DATA
from alert.routes import TriggerAlertRequest, trigger_alert_core

router = APIRouter(prefix="/api/simulation", tags=["simulation"])

sim_state = {}
auto_mode = False


def _init_factory_state(factory):
    fid = factory["id"]
    if fid not in sim_state:
        base = factory["base_temp"]
        sim_state[fid] = {
            "temperature": round(base + random.uniform(-3, 3), 1),
            "humidity": round(random.uniform(30, 60), 1),
            "smoke_level": round(random.uniform(5, 30), 1),
            "pressure": round(random.uniform(0.95, 1.15), 2),
            "status": "normal",
        }
    return sim_state[fid]


def _evaluate_status(state):
    t = state["temperature"]
    s = state["smoke_level"]
    h = state["humidity"]
    p = state["pressure"]

    if t >= 70 or s >= 80 or p >= 1.8:
        return "critical"
    if t >= 45 or s >= 50 or h >= 80 or h <= 20 or p >= 1.5:
        return "warning"
    return "normal"


def _random_step(current, base, spread=8, step=2):
    drift = random.uniform(-step, step)
    new_val = current + drift
    if abs(new_val - base) > spread:
        new_val = base + (spread if new_val > base else -spread) * random.uniform(0.5, 1.0)
    return round(new_val, 1)


class UpdateSensorRequest(BaseModel):
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    smoke_level: Optional[float] = None
    pressure: Optional[float] = None


@router.get("/state")
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
            "sensors": {
                "temperature": state.get("temperature", 0),
                "humidity": state.get("humidity", 0),
                "smoke_level": state.get("smoke_level", 0),
                "pressure": state.get("pressure", 0),
            },
        })
    return {"factories": result, "auto_mode": auto_mode}


@router.post("/update/{factory_id}")
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
        try:
            treq = TriggerAlertRequest(
                factory_id=factory["id"],
                factory_name=factory["name"],
                lat=factory["lat"],
                lon=factory["lon"],
                temperature=state["temperature"],
                smoke_level=state["smoke_level"],
                triggered_by="sensor",
            )
            await trigger_alert_core(treq)
        except Exception:
            pass

    return {"message": "Updated", "factory_id": factory_id, "status": state["status"]}


@router.post("/tick")
async def auto_tick():
    for factory in FACTORY_DATA:
        _init_factory_state(factory)
        state = sim_state[factory["id"]]
        base = factory["base_temp"]
        old_status = state.get("status", "normal")
        state["temperature"] = _random_step(state["temperature"], base, spread=10, step=3)
        state["smoke_level"] = _random_step(state["smoke_level"], 20, spread=25, step=5)
        state["humidity"] = _random_step(state["humidity"], 45, spread=20, step=4)
        state["pressure"] = _random_step(state["pressure"], 1.05, spread=0.4, step=0.03)
        state["status"] = _evaluate_status(state)

        if state["status"] == "critical" and old_status != "critical":
            try:
                req = TriggerAlertRequest(
                    factory_id=factory["id"],
                    factory_name=factory["name"],
                    lat=factory["lat"],
                    lon=factory["lon"],
                    temperature=state["temperature"],
                    smoke_level=state["smoke_level"],
                    triggered_by="sensor",
                )
                await trigger_alert_core(req)
            except Exception:
                pass

    return await get_simulation_state_async()


async def get_simulation_state_async():
    result = get_simulation_state()
    return result


@router.post("/trigger/{factory_id}")
async def manual_trigger(factory_id: int):
    factory = next((f for f in FACTORY_DATA if f["id"] == factory_id), None)
    if not factory:
        raise HTTPException(status_code=404, detail="Factory not found")
    _init_factory_state(factory)
    state = sim_state[factory_id]

    req = TriggerAlertRequest(
        factory_id=factory["id"],
        factory_name=factory["name"],
        lat=factory["lat"],
        lon=factory["lon"],
        temperature=state.get("temperature", 0),
        smoke_level=state.get("smoke_level", 0),
        triggered_by="manual",
    )
    try:
        result = await trigger_alert_core(req)
        return {"message": "Alert triggered", "alert_id": result.alert_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto")
def toggle_auto(mode: bool):
    global auto_mode
    auto_mode = mode
    return {"auto_mode": auto_mode}
