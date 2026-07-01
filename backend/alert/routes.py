from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from database import get_db, SessionLocal
from alert.models import Alert, AlertNotification
from geo.distance import find_nearest_stations
from geo.osm_client import fetch_stations_from_osm
from geo.routing import get_route
from config import ALERT_RADIUS_KM

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

stations_cache = []


class TriggerAlertRequest(BaseModel):
    factory_id: int
    factory_name: str
    lat: float
    lon: float
    temperature: Optional[float] = 0.0
    smoke_level: Optional[float] = 0.0
    triggered_by: Optional[str] = "sensor"


class TriggerAlertResponse(BaseModel):
    alert_id: int
    nearest_stations: list


async def ensure_stations_loaded():
    global stations_cache
    if not stations_cache:
        try:
            stations_cache = await fetch_stations_from_osm()
        except Exception as e:
            print(f"Failed to load stations: {e}")
            stations_cache = []


async def trigger_alert_core(req: TriggerAlertRequest):
    global stations_cache
    await ensure_stations_loaded()
    if not stations_cache:
        raise HTTPException(status_code=503, detail="Station data not available")

    db = SessionLocal()
    try:
        alert = Alert(
            factory_id=req.factory_id,
            factory_name=req.factory_name,
            lat=req.lat,
            lon=req.lon,
            temperature=req.temperature,
            smoke_level=req.smoke_level,
            status="active",
            triggered_by=req.triggered_by,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)

        nearest = find_nearest_stations(
            req.lat, req.lon, stations_cache, radius_km=ALERT_RADIUS_KM
        )

        for s in nearest:
            route = None
            try:
                route = await get_route(s["lat"], s["lon"], req.lat, req.lon)
            except Exception:
                pass

            notif = AlertNotification(
                alert_id=alert.id,
                station_id=s["id"],
                station_name=s["name"],
                station_type=s["type"],
                distance_km=s["distance_km"],
                eta_min=route["duration_min"] if route else None,
                notified=True,
            )
            db.add(notif)
        db.commit()
        return TriggerAlertResponse(alert_id=alert.id, nearest_stations=nearest)
    finally:
        db.close()


@router.post("/trigger", response_model=TriggerAlertResponse)
async def trigger_alert(req: TriggerAlertRequest, db: Session = Depends(get_db)):
    result = await trigger_alert_core(req)
    return result


@router.get("/active")
def get_active_alerts(db: Session = Depends(get_db)):
    alerts = db.query(Alert).filter(Alert.status == "active").order_by(Alert.created_at.desc()).all()
    result = []
    for a in alerts:
        notifs = db.query(AlertNotification).filter(
            AlertNotification.alert_id == a.id
        ).order_by(AlertNotification.distance_km).all()
        result.append({
            "id": a.id,
            "factory_id": a.factory_id,
            "factory_name": a.factory_name,
            "lat": a.lat,
            "lon": a.lon,
            "temperature": a.temperature,
            "smoke_level": a.smoke_level,
            "status": a.status,
            "triggered_by": a.triggered_by,
            "created_at": a.created_at.isoformat(),
            "notifications": [
                {
                    "station_id": n.station_id,
                    "station_name": n.station_name,
                    "station_type": n.station_type,
                    "distance_km": n.distance_km,
                    "eta_min": n.eta_min,
                }
                for n in notifs
            ],
        })
    return result


@router.get("/history")
def get_alert_history(db: Session = Depends(get_db)):
    alerts = db.query(Alert).order_by(Alert.created_at.desc()).limit(50).all()
    return [
        {
            "id": a.id,
            "factory_name": a.factory_name,
            "status": a.status,
            "created_at": a.created_at.isoformat(),
            "triggered_by": a.triggered_by,
        }
        for a in alerts
    ]


@router.get("/{alert_id}/route/{station_id}")
async def get_alert_route(alert_id: int, station_id: str, db: Session = Depends(get_db)):
    s = next((s for s in stations_cache if s["id"] == station_id), None)
    if not s:
        try:
            stations = await fetch_stations_from_osm()
            s = next((st for st in stations if st["id"] == station_id), None)
        except Exception:
            pass
    if not s:
        raise HTTPException(status_code=404, detail="Station not found")

    alert_obj = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert_obj:
        raise HTTPException(status_code=404, detail="Alert not found")

    route = await get_route(s["lat"], s["lon"], alert_obj.lat, alert_obj.lon)
    if not route:
        raise HTTPException(status_code=503, detail="Could not compute route")
    return route


@router.post("/resolve/{alert_id}")
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Alert resolved"}


@router.get("/stations")
async def get_stations():
    await ensure_stations_loaded()
    return stations_cache


@router.post("/refresh")
async def refresh_stations():
    global stations_cache
    stations_cache = await fetch_stations_from_osm()
    return {"count": len(stations_cache), "stations": stations_cache}
