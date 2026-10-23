"""
SmartGuard — Automated Backend API Test Suite
Covers:
  - Health check & database connection
  - Authentication validation & failure cases
  - Motion event ingestion (valid & invalid payloads)
  - Duplicate reading suppression / state-transition logic
  - System status & event audit log queries
  - Simulation requests from the dashboard
"""

import pytest
import json
from app import app, Session, init_db
from models import DeviceStatus, MotionEvent
from config import Config

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        # Clear test database before running tests
        with Session() as session:
            session.query(MotionEvent).delete()
            session.query(DeviceStatus).delete()
            session.commit()
        yield client

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
    with Session() as session:
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
    with Session() as session:
        events = session.query(MotionEvent).all()
        assert len(events) == 2

# 6. Status Endpoint Test
def test_status_endpoint(client):
    headers = {"X-API-Key": Config.API_KEY}
    client.post("/api/motion", json={"device_id": "esp32-pir-01", "state": "MOTION_DETECTED"}, headers=headers)

    response = client.get("/api/status")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["current_motion_state"] == "MOTION_DETECTED"
    assert data["is_online"] is True
    assert data["total_events"] == 1
    assert data["sensor_status_label"] == "Connected"

# 7. Recent Events Endpoint Test
def test_events_list_endpoint(client):
    headers = {"X-API-Key": Config.API_KEY}
    client.post("/api/motion", json={"device_id": "esp32-pir-01", "state": "MOTION_DETECTED"}, headers=headers)
    client.post("/api/motion", json={"device_id": "esp32-pir-01", "state": "NO_MOTION"}, headers=headers)

    response = client.get("/api/events?limit=10")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["count"] == 2
    assert len(data["events"]) == 2
    # Verify latest is first
    assert data["events"][0]["event_type"] == "NO_MOTION"
    assert data["events"][1]["event_type"] == "MOTION_DETECTED"

# 8. Simulated Event from Dashboard Test
def test_simulated_dashboard_event(client):
    payload = {
        "device_id": "dashboard-sim-01",
        "state": "MOTION_DETECTED",
        "gpio_pin": 27,
        "is_simulated": True,
        "details": "Simulated trigger by dashboard user"
    }
    # No API Key needed when is_simulated is True
    response = client.post("/api/motion", json=payload)
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["success"] is True
    assert data["event"]["is_simulated"] is True

# 9. Invalid Payload Test
def test_invalid_payload(client):
    headers = {"X-API-Key": Config.API_KEY}
    
    # Missing state
    res1 = client.post("/api/motion", json={"device_id": "esp32-pir-01"}, headers=headers)
    assert res1.status_code == 400

    # Illegal state name
    res2 = client.post("/api/motion", json={"device_id": "esp32-pir-01", "state": "INVALID_STATE"}, headers=headers)
    assert res2.status_code == 400
    assert "Invalid state" in json.loads(res2.data)["error"]
