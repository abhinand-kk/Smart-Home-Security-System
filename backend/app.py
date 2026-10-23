import os
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from config import Config
from models import init_db, DeviceStatus, MotionEvent

# Initialize Flask Application
app = Flask(__name__)
app.config.from_object(Config)

# Enable Cross-Origin Resource Sharing (CORS)
CORS(app, resources={r"/api/*": {"origins": Config.CORS_ORIGINS}})

# Initialize Database
engine, Session = init_db(Config.SQLALCHEMY_DATABASE_URI)

# Helper function to check API key authentication
def authenticate_request():
    """Validates API Key from X-API-Key header, Bearer token, or query param."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:].strip()
    if not api_key:
        api_key = request.args.get("api_key")
        
    return api_key == Config.API_KEY


# -----------------------------------------------------------------------------
# 1. Health Check Endpoint
# -----------------------------------------------------------------------------
@app.route("/api/health", methods=["GET"])
def health_check():
    """Verify backend status and database connectivity."""
    db_ok = False
    try:
        with Session() as session:
            # Simple query to verify connection
            session.query(DeviceStatus).first()
            db_ok = True
    except Exception as e:
        app.logger.error(f"Database health check failed: {e}")

    return jsonify({
        "status": "healthy" if db_ok else "degraded",
        "database": {
            "connected": db_ok,
            "type": Config.DB_TYPE
        },
        "server_time": datetime.now(timezone.utc).isoformat(),
        "service": "SmartGuard IoT Motion Backend",
        "version": "1.0.0"
    }), 200 if db_ok else 503


# -----------------------------------------------------------------------------
# 2. Ingest Motion Event / Heartbeat (ESP32 or Dashboard Simulation)
# -----------------------------------------------------------------------------
@app.route("/api/motion", methods=["POST"])
def record_motion():
    """
    Ingest a motion event or heartbeat from ESP32 or simulation.
    Records state transitions to prevent duplicate spam.
    """
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Invalid request body; JSON required"}), 400

    # Device authentication check (Allows simulation if explicit demo flag is sent with valid demo header)
    is_simulated = bool(payload.get("is_simulated", False))
    if not is_simulated and not authenticate_request():
        return jsonify({"error": "Unauthorized: Invalid or missing API key"}), 401

    # Extract & validate fields
    device_id = payload.get("device_id", "esp32-pir-01").strip()
    if not device_id:
        return jsonify({"error": "Missing required field: device_id"}), 400

    raw_state = str(payload.get("state", "")).strip().upper()
    valid_states = {"MOTION_DETECTED", "NO_MOTION", "HEARTBEAT"}
    if raw_state not in valid_states:
        return jsonify({
            "error": f"Invalid state '{raw_state}'. Allowed values: {list(valid_states)}"
        }), 400

    gpio_pin = int(payload.get("gpio_pin", 27))
    client_ip = payload.get("ip_address") or request.remote_addr
    now_utc = datetime.now(timezone.utc)

    with Session() as session:
        # Find or create device record
        device = session.query(DeviceStatus).filter_by(device_id=device_id).first()
        if not device:
            device = DeviceStatus(
                device_id=device_id,
                device_name=payload.get("device_name", "ESP32 Motion Sensor"),
                current_motion_state="NO_MOTION",
                gpio_pin=gpio_pin,
                is_online=True,
                last_seen_at=now_utc,
                ip_address=client_ip
            )
            session.add(device)
            session.flush()

        previous_state = device.current_motion_state
        is_transition = False
        new_event = None

        if raw_state == "HEARTBEAT":
            # Heartbeats update heartbeat timestamp without state transition
            device.last_seen_at = now_utc
            device.is_online = True
            if client_ip:
                device.ip_address = client_ip
            message = "Heartbeat recorded successfully"
        else:
            # Motion state update
            device.last_seen_at = now_utc
            device.is_online = True
            if client_ip:
                device.ip_address = client_ip

            if raw_state == "MOTION_DETECTED":
                device.last_motion_at = now_utc

            # Meaningful state transition check
            if raw_state != previous_state or device.last_motion_at is None:
                is_transition = True
                device.current_motion_state = raw_state
                
                new_event = MotionEvent(
                    device_id=device_id,
                    event_type=raw_state,
                    previous_state=previous_state,
                    gpio_pin=gpio_pin,
                    timestamp=now_utc,
                    is_simulated=is_simulated,
                    details=payload.get("details", f"State transition: {previous_state} -> {raw_state}")
                )
                session.add(new_event)
                message = f"State transition recorded: {raw_state}"
            else:
                # Repeated identical reading: update last seen but do not duplicate event history
                message = f"State maintained ({raw_state}); duplicate event avoided"

        session.commit()

        return jsonify({
            "success": True,
            "message": message,
            "state_transition": is_transition,
            "current_state": device.current_motion_state,
            "event": new_event.to_dict() if new_event else None,
            "device": device.to_dict(is_online_override=True)
        }), 201 if is_transition else 200


# -----------------------------------------------------------------------------
# 3. Overall Dashboard Status
# -----------------------------------------------------------------------------
@app.route("/api/status", methods=["GET"])
def get_status():
    """Returns current motion state, online/offline status, and summary metrics."""
    now_utc = datetime.now(timezone.utc)
    timeout = timedelta(seconds=Config.HEARTBEAT_TIMEOUT_SECONDS)

    with Session() as session:
        device = session.query(DeviceStatus).first()
        total_events = session.query(MotionEvent).count()
        recent_event = session.query(MotionEvent).order_by(MotionEvent.timestamp.desc()).first()

        if not device:
            # Default response when no device has registered yet
            return jsonify({
                "current_motion_state": "NO_MOTION",
                "is_online": False,
                "sensor_status_label": "Not Connected",
                "last_seen_at": None,
                "last_motion_at": None,
                "total_events": 0,
                "database_type": Config.DB_TYPE,
                "device": None
            }), 200

        # Compute online state based on timeout
        is_online = (now_utc - device.last_seen_at.replace(tzinfo=timezone.utc)) < timeout

        return jsonify({
            "current_motion_state": device.current_motion_state,
            "is_online": is_online,
            "sensor_status_label": "Connected" if is_online else "Offline (Connection Pending)",
            "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
            "last_motion_at": device.last_motion_at.isoformat() if device.last_motion_at else None,
            "total_events": total_events,
            "last_event": recent_event.to_dict() if recent_event else None,
            "database_type": Config.DB_TYPE,
            "device": device.to_dict(is_online_override=is_online)
        }), 200


# -----------------------------------------------------------------------------
# 4. Motion History Events List
# -----------------------------------------------------------------------------
@app.route("/api/events", methods=["GET"])
def get_events():
    """Retrieve timestamped motion events for the Recent Activity table."""
    limit = min(int(request.args.get("limit", 20)), 100)
    device_id = request.args.get("device_id")
    event_type = request.args.get("event_type")

    with Session() as session:
        query = session.query(MotionEvent)
        
        if device_id:
            query = query.filter_by(device_id=device_id)
        if event_type:
            query = query.filter_by(event_type=event_type)

        events = query.order_by(MotionEvent.timestamp.desc()).limit(limit).all()
        return jsonify({
            "count": len(events),
            "events": [e.to_dict() for e in events]
        }), 200


# -----------------------------------------------------------------------------
# 5. Reset / Seed Demo History (Safe testing helper)
# -----------------------------------------------------------------------------
@app.route("/api/events/clear", methods=["POST"])
def clear_events():
    """Clear demonstration events for clean test runs."""
    with Session() as session:
        session.query(MotionEvent).delete()
        session.commit()
    return jsonify({"success": True, "message": "Event history cleared"}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1")
    print(f"Starting SmartGuard Flask Backend on port {port} (Database: {Config.DB_TYPE})...")
    app.run(host="0.0.0.0", port=port, debug=debug)
