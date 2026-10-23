from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class DeviceStatus(Base):
    """Stores the latest state of an IoT device separately from historical logs."""
    __tablename__ = "device_status"

    id = Column(Integer, primary_key=True)
    device_id = Column(String(64), unique=True, nullable=False, index=True)
    device_name = Column(String(128), default="ESP32 Motion Sensor")
    current_motion_state = Column(String(32), default="NO_MOTION", nullable=False)
    gpio_pin = Column(Integer, default=27)
    is_online = Column(Boolean, default=False)
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_motion_at = Column(DateTime, nullable=True)
    ip_address = Column(String(45), nullable=True)
    firmware_version = Column(String(32), default="1.0.0")

    def to_dict(self, is_online_override=None):
        online = self.is_online if is_online_override is None else is_online_override
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "current_motion_state": self.current_motion_state,
            "gpio_pin": self.gpio_pin,
            "is_online": online,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "last_motion_at": self.last_motion_at.isoformat() if self.last_motion_at else None,
            "ip_address": self.ip_address,
            "firmware_version": self.firmware_version
        }


class MotionEvent(Base):
    """Stores audit history for meaningful motion state transitions and heartbeats."""
    __tablename__ = "motion_events"

    id = Column(Integer, primary_key=True)
    device_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(32), nullable=False, index=True)  # MOTION_DETECTED, NO_MOTION, HEARTBEAT
    previous_state = Column(String(32), nullable=True)
    gpio_pin = Column(Integer, default=27)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    is_simulated = Column(Boolean, default=False, nullable=False)
    details = Column(Text, nullable=True)

    def to_dict(self):
        # Format friendly date and time strings for the frontend table
        dt = self.timestamp
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
            
        return {
            "id": self.id,
            "device_id": self.device_id,
            "event_type": self.event_type,
            "previous_state": self.previous_state,
            "gpio_pin": self.gpio_pin,
            "timestamp": dt.isoformat(),
            "formatted_date": dt.strftime("%Y-%m-%d"),
            "formatted_time": dt.strftime("%I:%M:%S %p"),
            "is_simulated": self.is_simulated,
            "details": self.details or ""
        }


def init_db(database_uri):
    """Initialize database tables and return engine and sessionmaker."""
    engine = create_engine(database_uri, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session
