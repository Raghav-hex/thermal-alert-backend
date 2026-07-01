from fastapi import APIRouter, HTTPException
import httpx
from config import FACTORY_DATA, CRITICAL_THRESHOLD_SMOKE
from alert.routes import TriggerAlertRequest, trigger_alert_core

router = APIRouter(prefix="/api/esp32", tags=["esp32"])

FIREBASE_URL = "https://sivakasi-fire-default-rtdb.asia-southeast1.firebasedatabase.app"


@router.get("/smoke/{factory_id}")
async def get_esp32_smoke(factory_id: int):
    factory = next((f for f in FACTORY_DATA if f["id"] == factory_id), None)
    if not factory:
        raise HTTPException(status_code=404, detail="Factory not found")

    url = f"{FIREBASE_URL}/esp32/factory_{factory_id}/smoke_level.json"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        if resp.status_code == 404:
            return {
                "factory_id": factory_id,
                "factory_name": factory["name"],
                "smoke_level": None,
                "source": "none",
            }
        resp.raise_for_status()
        smoke_level = resp.json()

    return {
        "factory_id": factory_id,
        "factory_name": factory["name"],
        "smoke_level": smoke_level,
        "source": "esp32" if smoke_level is not None else "none",
    }


@router.get("/smoke")
async def get_all_esp32_smoke():
    url = f"{FIREBASE_URL}/esp32.json"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        if resp.status_code == 404:
            return {}
        resp.raise_for_status()
        return resp.json() or {}


@router.post("/check")
async def check_esp32_alerts():
    url = f"{FIREBASE_URL}/esp32.json"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        if resp.status_code == 404 or not resp.json():
            return {"checked": True, "alerts_triggered": 0}
        esp32_data = resp.json()

    count = 0
    for key, data in esp32_data.items():
        if not isinstance(data, dict):
            continue
        smoke_level = data.get("smoke_level")
        if not isinstance(smoke_level, (int, float)):
            continue
        if smoke_level >= CRITICAL_THRESHOLD_SMOKE:
            fid_str = key.replace("factory_", "")
            try:
                fid = int(fid_str)
            except ValueError:
                continue
            factory = next((f for f in FACTORY_DATA if f["id"] == fid), None)
            if not factory:
                continue
            try:
                req = TriggerAlertRequest(
                    factory_id=factory["id"],
                    factory_name=factory["name"],
                    lat=factory["lat"],
                    lon=factory["lon"],
                    temperature=0.0,
                    smoke_level=smoke_level,
                    triggered_by="esp32",
                )
                await trigger_alert_core(req)
                count += 1
            except Exception:
                pass

    return {"checked": True, "alerts_triggered": count}
