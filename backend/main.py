import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from database import engine, Base

import auth.models
import alert.models

Base.metadata.create_all(bind=engine)

from sqlalchemy import inspect, text
inspector = inspect(engine)
columns = [c["name"] for c in inspector.get_columns("users")]
with engine.connect() as conn:
    if "role" not in columns:
        conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'admin'"))
    if "factory_id" not in columns:
        conn.execute(text("ALTER TABLE users ADD COLUMN factory_id INTEGER"))
    conn.commit()

from config import FACTORY_DATA

app = FastAPI(title="Thermal Alert System - Sivakasi")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from auth.routes import router as auth_router
from alert.routes import router as alert_router
from simulation.routes import router as sim_router
from esp32.routes import router as esp32_router
from camera.routes import router as camera_router

app.include_router(auth_router)
app.include_router(alert_router)
app.include_router(sim_router)
app.include_router(esp32_router)
app.include_router(camera_router)


@app.get("/api/factories")
def get_factories():
    return FACTORY_DATA


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Thermal Alert System - Sivakasi"}


FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")


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
