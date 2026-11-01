"""
SmartGuard — Automated Backend API Test Suite
Covers:
  - Health check & database connection
  - Authentication validation & failure cases
  - Valid physical motion ingest & duplicate reading suppression
  - Physical device heartbeat handling (keep-alive pings)
  - Simulation isolation (ensuring dashboard tests never overwrite physical hardware)
  - Online / offline transition logic based on heartbeat timeouts
  - System status response compatibility & field requirements
  - Production CORS origin headers
  - Recent events audit logs & filtering
  - Invalid payload handling
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import app as app_module
from app import app
from models import Base, DeviceStatus, MotionEvent
from config import Config

# Initialize isolated in-memory test database for test runs
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
Base.metadata.create_all(test_engine)
TestSession = sessionmaker(bind=test_engine)
app_module.Session = TestSession
app_module.engine = test_engine

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        # Clear test database before each test
        with TestSession() as session:
            session.query(MotionEvent).delete()
            session.query(DeviceStatus).delete()
            session.commit()
        yield client
        with TestSession() as session:
            session.query(MotionEvent).delete()
            session.query(DeviceStatus).delete()
            session.commit()

# 1. Health Endpoint Test
def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "healthy"
    assert data["database"]["connected"] is True
    assert "type" in data["database"]

# 2. Authentication Failure Test (Invalid or missing API Key)
def test_authentication_failure(client):
    payload = {
        "device_id": "esp32-pir-01",
        "state": "MOTION_DETECTED",
        "gpio_pin": 27,
        "is_simulated": False
    }
    # Request without X-API-Key header
    response = client.post("/api/motion", json=payload)
    assert response.status_code == 401
    data = json.loads(response.data)
    assert "Unauthorized" in data["error"]

    # Request with WRONG API Key
    response = client.post("/api/motion", json=payload, headers={"X-API-Key": "wrong-secret-key"})
    assert response.status_code == 401

# 3. Valid Motion Ingest with Authentication Test
def test_valid_motion_ingest_with_auth(client):
    payload = {
        "device_id": "esp32-pir-01",
        "state": "MOTION_DETECTED",
        "gpio_pin": 27,
        "is_simulated": False,
        "details": "PIR interrupt pulse on GPIO 27"
    }
    response = client.post("/api/motion", json=payload, headers={"X-API-Key": Config.API_KEY})
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["success"] is True
    assert data["state_transition"] is True
    assert data["current_state"] == "MOTION_DETECTED"
    assert data["device"]["is_online"] is True
    assert data["device"]["device_id"] == "esp32-pir-01"

# 4. Duplicate Reading Suppression (State-transition check)
def test_duplicate_reading_suppression(client):
    headers = {"X-API-Key": Config.API_KEY}
    payload = {
        "device_id": "esp32-pir-01",
        "state": "MOTION_DETECTED",
        "gpio_pin": 27
    }

    # First event: Transition to MOTION_DETECTED -> 201 Created
    res1 = client.post("/api/motion", json=payload, headers=headers)
    assert res1.status_code == 201

    # Second event: Exact same state -> 200 OK (no duplicate row)
    res2 = client.post("/api/motion", json=payload, headers=headers)
    assert res2.status_code == 200
    data2 = json.loads(res2.data)
    assert data2["state_transition"] is False
    assert "duplicate event avoided" in data2["message"]

    # Verify only 1 event exists in database
    with TestSession() as session:
        count = session.query(MotionEvent).count()
        assert count == 1

# 5. Motion Cleared Transition Test
def test_motion_cleared_transition(client):
    headers = {"X-API-Key": Config.API_KEY}
    
    # 1. Trigger motion
    client.post("/api/motion", json={"device_id": "esp32-pir-01", "state": "MOTION_DETECTED"}, headers=headers)
    
    # 2. Reset / Clear motion
    res = client.post("/api/motion", json={"device_id": "esp32-pir-01", "state": "NO_MOTION"}, headers=headers)
    assert res.status_code == 201
    data = json.loads(res.data)
    assert data["current_state"] == "NO_MOTION"
    assert data["state_transition"] is True

    # Total 2 events in database
    with TestSession() as session:
        events = session.query(MotionEvent).all()
        assert len(events) == 2

# 6. Physical Device Heartbeat Handling Test
def test_physical_device_heartbeat_handling(client):
    headers = {"X-API-Key": Config.API_KEY}
    
    # Send periodic heartbeat
    payload = {
        "device_id": "esp32-pir-01",
        "state": "HEARTBEAT",
        "gpio_pin": 27,
        "is_simulated": False,
        "details": "Periodic sensor health keep-alive"
    }
    response = client.post("/api/motion", json=payload, headers=headers)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert data["state_transition"] is False
    assert "Heartbeat recorded" in data["message"]

    # Heartbeat must NOT insert a MotionEvent row
    with TestSession() as session:
        count = session.query(MotionEvent).count()
        assert count == 0
        
        # Must update DeviceStatus last_seen_at
        dev = session.query(DeviceStatus).filter_by(device_id="esp32-pir-01").first()
        assert dev is not None
        assert dev.last_seen_at is not None

# 7. Simulation Isolation from Physical Device Test
def test_simulation_isolation_from_physical_device(client):
    headers = {"X-API-Key": Config.API_KEY}
    
    # 1. Physical hardware sends genuine NO_MOTION state
    client.post("/api/motion", json={
        "device_id": "esp32-pir-01",
        "state": "NO_MOTION",
        "is_simulated": False
    }, headers=headers)

    # 2. Dashboard user triggers a simulation event
    sim_res = client.post("/api/motion", json={
        "device_id": "dashboard-sim-01",
        "state": "MOTION_DETECTED",
        "is_simulated": True,
        "details": "Simulated trigger by dashboard user"
    })
    assert sim_res.status_code == 201

    # 3. Verify /api/status still reports the physical ESP32 device
    status_res = client.get("/api/status")
    assert status_res.status_code == 200
    status_data = json.loads(status_res.data)

    # Physical device state MUST NOT be overwritten by the simulation
    assert status_data["device_id"] == "esp32-pir-01"
    assert status_data["current_motion_state"] == "NO_MOTION"
    assert status_data["is_online"] is True
    assert status_data["device"]["device_id"] == "esp32-pir-01"

    # Even if simulation passes device_id="esp32-pir-01" without auth, it must be forced to simulation ID
    malicious_sim = client.post("/api/motion", json={
        "device_id": "esp32-pir-01",
        "state": "MOTION_DETECTED",
        "is_simulated": True
    })
    assert malicious_sim.status_code in [200, 201]
    
    # Physical device still intact
    status_check = client.get("/api/status")
    status_check_data = json.loads(status_check.data)
    assert status_check_data["device_id"] == "esp32-pir-01"
    assert status_check_data["current_motion_state"] == "NO_MOTION"

# 8. Online / Offline Transition Logic Test
def test_online_offline_transitions(client):
    headers = {"X-API-Key": Config.API_KEY}
    
    # 1. Register active device
    client.post("/api/motion", json={
        "device_id": "esp32-pir-01",
        "state": "HEARTBEAT",
        "is_simulated": False
    }, headers=headers)

    res_online = client.get("/api/status")
    assert res_online.status_code == 200
    assert json.loads(res_online.data)["is_online"] is True
    assert json.loads(res_online.data)["sensor_status_label"] == "Connected"

    # 2. Simulate expired heartbeat (e.g. 100 seconds ago)
    with TestSession() as session:
        dev = session.query(DeviceStatus).filter_by(device_id="esp32-pir-01").first()
        dev.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=100)
        session.commit()

    res_offline = client.get("/api/status")
    assert res_offline.status_code == 200
    assert json.loads(res_offline.data)["is_online"] is False
    assert json.loads(res_offline.data)["sensor_status_label"] == "Offline (Connection Pending)"

    # 3. New heartbeat revives online state immediately
    client.post("/api/motion", json={
        "device_id": "esp32-pir-01",
        "state": "HEARTBEAT",
        "is_simulated": False
    }, headers=headers)

    res_revived = client.get("/api/status")
    assert res_revived.status_code == 200
    assert json.loads(res_revived.data)["is_online"] is True
    assert json.loads(res_revived.data)["sensor_status_label"] == "Connected"

# 9. API Status Response Compatibility Test
def test_api_status_compatibility(client):
    headers = {"X-API-Key": Config.API_KEY}
    client.post("/api/motion", json={"device_id": "esp32-pir-01", "state": "MOTION_DETECTED"}, headers=headers)

    res = client.get("/api/status")
    assert res.status_code == 200
    data = json.loads(res.data)

    # Required contract fields
    expected_fields = [
        "current_motion_state",
        "is_online",
        "sensor_status_label",
        "device_id",
        "device_name",
        "last_seen_at",
        "last_motion_at",
        "total_events",
        "last_event",
        "database_type",
        "heartbeat_timeout_seconds",
        "device"
    ]
    for field in expected_fields:
        assert field in data, f"Missing required response field: {field}"

    assert data["device_id"] == "esp32-pir-01"
    assert data["device"]["device_id"] == "esp32-pir-01"
    assert data["current_motion_state"] == "MOTION_DETECTED"

# 10. CORS Headers for Production Origin Test
def test_production_cors_headers(client):
    prod_origin = "https://smart-home-security-system-backend.vercel.app"
    
    # Preflight request
    res_opt = client.options("/api/status", headers={
        "Origin": prod_origin,
        "Access-Control-Request-Method": "GET"
    })
    assert res_opt.status_code == 200
    assert res_opt.headers.get("Access-Control-Allow-Origin") in [prod_origin, "*"]

    # Direct GET request
    res_get = client.get("/api/status", headers={"Origin": prod_origin})
    assert res_get.status_code == 200
    assert res_get.headers.get("Access-Control-Allow-Origin") in [prod_origin, "*"]

# 11. Recent Events Endpoint Test
def test_events_list_endpoint(client):
    headers = {"X-API-Key": Config.API_KEY}
    client.post("/api/motion", json={"device_id": "esp32-pir-01", "state": "MOTION_DETECTED"}, headers=headers)
    client.post("/api/motion", json={"device_id": "esp32-pir-01", "state": "NO_MOTION"}, headers=headers)

    response = client.get("/api/events?limit=10")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["count"] == 2
    assert len(data["events"]) == 2
    assert data["events"][0]["event_type"] == "NO_MOTION"
    assert data["events"][1]["event_type"] == "MOTION_DETECTED"

# 12. Invalid Payload Test
def test_invalid_payload(client):
    headers = {"X-API-Key": Config.API_KEY}
    
    # Missing state
    res1 = client.post("/api/motion", json={"device_id": "esp32-pir-01"}, headers=headers)
    assert res1.status_code == 400

    # Illegal state name
    res2 = client.post("/api/motion", json={"device_id": "esp32-pir-01", "state": "INVALID_STATE"}, headers=headers)
    assert res2.status_code == 400
    assert "Invalid state" in json.loads(res2.data)["error"]

# 13. Heartbeat State Reconciliation (Self-healing from missed NO_MOTION)
def test_heartbeat_state_reconciliation_when_sensor_quiet(client):
    headers = {"X-API-Key": Config.API_KEY}

    # Step 1: Device enters MOTION_DETECTED
    res1 = client.post("/api/motion", json={
        "device_id": "esp32-pir-01",
        "state": "MOTION_DETECTED",
        "gpio_pin": 27
    }, headers=headers)
    assert res1.status_code == 201
    assert json.loads(res1.data)["current_state"] == "MOTION_DETECTED"

    # Verify status reports MOTION_DETECTED
    status1 = client.get("/api/status")
    assert json.loads(status1.data)["current_motion_state"] == "MOTION_DETECTED"

    # Step 2: Device sends a periodic HEARTBEAT reporting physical sensor is LOW (pir_state = 0)
    # This simulates recovery when a NO_MOTION transition packet was dropped or missed
    hb_payload = {
        "device_id": "esp32-pir-01",
        "state": "HEARTBEAT",
        "gpio_pin": 27,
        "pir_state": 0,
        "motion_detected": False,
        "details": "Periodic keep-alive ping"
    }
    hb_res = client.post("/api/motion", json=hb_payload, headers=headers)
    assert hb_res.status_code == 201  # Transition reconciled!
    hb_data = json.loads(hb_res.data)
    assert hb_data["current_state"] == "NO_MOTION"
    assert hb_data["state_transition"] is True

    # Step 3: Status now reports NO_MOTION while maintaining is_online = True
    status2 = client.get("/api/status")
    status2_data = json.loads(status2.data)
    assert status2_data["current_motion_state"] == "NO_MOTION"
    assert status2_data["is_online"] is True
    assert status2_data["sensor_status_label"] == "Connected"

# 14. Bidirectional Motion Cycle Test (Full HIGH-to-LOW transition cycle)
def test_bidirectional_motion_cycle(client):
    headers = {"X-API-Key": Config.API_KEY}

    # Initial state: NO_MOTION
    client.post("/api/motion", json={"device_id": "esp32-pir-01", "state": "NO_MOTION"}, headers=headers)
    s0 = json.loads(client.get("/api/status").data)
    assert s0["current_motion_state"] == "NO_MOTION"
    assert s0["is_online"] is True

    # Transition 1: Person enters -> MOTION_DETECTED
    client.post("/api/motion", json={"device_id": "esp32-pir-01", "state": "MOTION_DETECTED"}, headers=headers)
    s1 = json.loads(client.get("/api/status").data)
    assert s1["current_motion_state"] == "MOTION_DETECTED"
    assert s1["is_online"] is True

    # Transition 2: Person moves away -> NO_MOTION
    client.post("/api/motion", json={"device_id": "esp32-pir-01", "state": "NO_MOTION"}, headers=headers)
    s2 = json.loads(client.get("/api/status").data)
    assert s2["current_motion_state"] == "NO_MOTION"
    assert s2["is_online"] is True

    # Transition 3: Person enters again -> MOTION_DETECTED
    client.post("/api/motion", json={"device_id": "esp32-pir-01", "state": "MOTION_DETECTED"}, headers=headers)
    s3 = json.loads(client.get("/api/status").data)
    assert s3["current_motion_state"] == "MOTION_DETECTED"
    assert s3["is_online"] is True

    # Transition 4: Person moves away again -> NO_MOTION
    client.post("/api/motion", json={"device_id": "esp32-pir-01", "state": "NO_MOTION"}, headers=headers)
    s4 = json.loads(client.get("/api/status").data)
    assert s4["current_motion_state"] == "NO_MOTION"
    assert s4["is_online"] is True

# 15. Device Online Status Distinguished from Motion Status (Requirement 5)
def test_device_online_status_distinguished_from_motion(client):
    headers = {"X-API-Key": Config.API_KEY}

    # Physical device is online sending heartbeats, but no motion
    client.post("/api/motion", json={
        "device_id": "esp32-pir-01",
        "state": "NO_MOTION",
        "gpio_pin": 27,
        "is_simulated": False
    }, headers=headers)

    client.post("/api/motion", json={
        "device_id": "esp32-pir-01",
        "state": "HEARTBEAT",
        "pir_state": 0,
        "is_simulated": False
    }, headers=headers)

    res = client.get("/api/status")
    data = json.loads(res.data)

    # Online status must be True, but motion status must be NO_MOTION
    assert data["is_online"] is True
    assert data["sensor_status_label"] == "Connected"
    assert data["current_motion_state"] == "NO_MOTION"

# 16. Simulation Isolation During Motion Transitions (Requirement 8)
def test_simulation_isolation_during_motion_transitions(client):
    headers = {"X-API-Key": Config.API_KEY}

    # Physical hardware is in NO_MOTION
    client.post("/api/motion", json={
        "device_id": "esp32-pir-01",
        "state": "NO_MOTION",
        "is_simulated": False
    }, headers=headers)

    # Simulation fires MOTION_DETECTED multiple times
    for _ in range(3):
        client.post("/api/motion", json={
            "device_id": "dashboard-sim-01",
            "state": "MOTION_DETECTED",
            "is_simulated": True
        })

    # Physical status remains strictly NO_MOTION
    status = json.loads(client.get("/api/status").data)
    assert status["device_id"] == "esp32-pir-01"
    assert status["current_motion_state"] == "NO_MOTION"
    assert status["is_online"] is True
