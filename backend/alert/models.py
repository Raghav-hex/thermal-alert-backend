from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from datetime import datetime, timezone
from database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, nullable=False)
    factory_name = Column(String(200), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    temperature = Column(Float, default=0.0)
    smoke_level = Column(Float, default=0.0)
    status = Column(String(50), default="active")
    triggered_by = Column(String(100), default="sensor")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)


class AlertNotification(Base):
    __tablename__ = "alert_notifications"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, nullable=False)
    station_id = Column(String(100), nullable=False)
    station_name = Column(String(200), nullable=False)
    station_type = Column(String(50), nullable=False)
    distance_km = Column(Float, nullable=False)
    eta_min = Column(Float, nullable=True)
    notified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
