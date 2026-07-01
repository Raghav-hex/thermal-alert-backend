from fastapi import APIRouter, HTTPException
import httpx
from config import FACTORY_DATA

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
