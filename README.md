# Smart Home Motion Monitoring System (IoT)

A complete, full-stack, college IoT project integrating an **ESP32 microcontroller**, a **PIR motion sensor (HC-SR501)**, a **Python Flask REST API**, a **PostgreSQL database (with SQLite local fallback)**, and a modern, responsive web dashboard.

---

## 📑 Table of Contents
1. [Project Overview & Architecture](#-project-overview--architecture)
2. [Hardware Wiring & Pinout Guide](#-hardware-wiring--pinout-guide)
3. [Database Schema (Dual Support: PostgreSQL & SQLite)](#-database-schema)
4. [Quick Start: Running Locally](#-quick-start-running-locally)
   - [Method A: Running with Docker Compose (Recommended)](#method-a-running-with-docker-compose-recommended)
   - [Method B: Running Standalone without Docker (SQLite Fallback)](#method-b-running-standalone-without-docker-sqlite-fallback)
5. [ESP32 Firmware Setup](#-esp32-firmware-setup)
6. [API Endpoints Reference](#-api-endpoints-reference)
7. [Automated Test Suite & Verification Results](#-automated-test-suite--verification-results)
8. [Free-Tier Cloud Deployment Guide](#-free-tier-cloud-deployment-guide)
9. [College Assignment Report Outline](#-college-assignment-report-outline)

---

## 🏗️ Project Overview & Architecture

The system provides autonomous real-time motion detection for smart homes:
1. When movement occurs in front of the **HC-SR501 PIR sensor**, it asserts a 3.3V digital logic `HIGH` on **GPIO 27** of the **ESP32**.
2. The ESP32 debounces the signal and dispatches an authenticated HTTP POST JSON request (`X-API-Key`) over Wi-Fi to the central **Python Flask API**.
3. The Flask API validates the request, records meaningful **state transitions** (preventing duplicate spam), updates device status, and saves a timestamped record to **PostgreSQL**.
4. The web dashboard continuously polls the Flask API every 2 seconds, displaying live motion status, hardware connectivity, and the recent activity audit log.

### Architecture Flow Diagram
```
┌─────────────────────────────────┐
│     HC-SR501 PIR Sensor         │
│  (120° FOV, 7m detection cone)  │
└────────────────┬────────────────┘
                 │ Digital Output (3.3V)
                 ▼
┌─────────────────────────────────┐
│       ESP32 Microcontroller     │
│   (GPIO 27 Digital Input Pin)   │
│   (Wi-Fi STA, HTTP Client)      │
└────────────────┬────────────────┘
                 │ HTTP POST JSON (with X-API-Key)
                 │ Port 5000 /api/motion
                 ▼
┌─────────────────────────────────┐
│       Python Flask API          │
│   (Gunicorn / WSGI, Port 5000)  │
│   (CORS, Auth, State Logic)     │
└───────┬─────────────────▲───────┘
        │ Read/Write      │ Polls /api/status
        │ SQLAlchemy      │ & /api/events (2s)
        ▼                 │
┌─────────────────┐ ┌─────┴────────────────────────┐
│ PostgreSQL 16   │ │ Smart Home Web Dashboard     │
│ (Persistent Vol)│ │ (HTML5, CSS3, Vanilla JS)    │
│ [Fallback SQLite│ │ (Desktop / Tablet / Mobile)  │
└─────────────────┘ └──────────────────────────────┘
```

---

## 🔌 Hardware Wiring & Pinout Guide

| HC-SR501 PIR Pin | ESP32 Pin | Wire Color (Typical) | Electrical Function |
| :--- | :--- | :--- | :--- |
| **VCC** | **VIN (5V)** | Red | Power supply (4.5V - 12V DC) |
| **OUT** | **GPIO 27** | Yellow / Blue | Digital signal (3.3V TTL logic HIGH on motion) |
| **GND** | **GND** | Black | Common ground reference |

> **Hardware Safety Note:** The HC-SR501 sensor natively outputs a 3.3V TTL signal on its `OUT` pin. This is directly safe for the ESP32 GPIO inputs without requiring any level-shifter resistor divider.

---

## 🗄️ Database Schema

The database supports **PostgreSQL** (inside Docker) and automatically falls back to **SQLite** (`backend/smartguard.db`) when run standalone.

### Table 1: `device_status`
Stores current device health separately from event logs:
- `id` (INTEGER, Primary Key)
- `device_id` (VARCHAR(64), Unique, Indexed) — e.g., `"esp32-pir-01"`
- `device_name` (VARCHAR(128)) — e.g., `"ESP32 Motion Sensor"`
- `current_motion_state` (VARCHAR(32)) — `"MOTION_DETECTED"` or `"NO_MOTION"`
- `gpio_pin` (INTEGER) — default `27`
- `is_online` (BOOLEAN) — calculated via heartbeat timeout (default 45s)
- `last_seen_at` (TIMESTAMP) — updated on every event or heartbeat
- `last_motion_at` (TIMESTAMP, Nullable) — updated when motion is detected
- `ip_address` (VARCHAR(45)) — local IP of the ESP32

### Table 2: `motion_events`
Stores historical audit logs for meaningful state transitions:
- `id` (INTEGER, Primary Key)
- `device_id` (VARCHAR(64), Indexed)
- `event_type` (VARCHAR(32)) — `"MOTION_DETECTED"`, `"NO_MOTION"`, or `"HEARTBEAT"`
- `previous_state` (VARCHAR(32)) — previous state before transition
- `gpio_pin` (INTEGER)
- `timestamp` (TIMESTAMP, Indexed) — UTC timestamp
- `is_simulated` (BOOLEAN) — `true` for dashboard simulations, `false` for real hardware
- `details` (TEXT) — contextual description

---

## 💻 Quick Start: Running Locally

### Method A: Running with Docker Compose (Recommended)

1. **Verify Docker Desktop is running on Windows.**
2. Open PowerShell or Terminal in this folder:
   ```powershell
   # Ensure environment variables are loaded
   Copy-Item .env.example .env -Force

   # Start PostgreSQL and Flask Backend containers
   docker compose up -d --build
   ```
3. **Verify the containers are healthy:**
   ```powershell
   docker compose ps
   ```
4. **Open the frontend website:**
   You can serve the frontend with Python:
   ```powershell
   python -m http.server 8080
   ```
   Then open your browser to [http://localhost:8080](http://localhost:8080).
   The dashboard will automatically connect to your backend at `http://localhost:5000/api`.

---

### Method B: Running Standalone without Docker (SQLite Fallback)

If your grading rubric or computer prefers running Python directly without Docker:

1. **Install backend dependencies:**
   ```powershell
   python -m pip install -r backend/requirements.txt
   ```
2. **Run the Flask server:**
   ```powershell
   python backend/app.py
   ```
   *(The server will detect that no PostgreSQL URL is set and will automatically initialize `backend/smartguard.db` using SQLite).*
3. **Open the frontend:**
   Open `index.html` in your browser or run:
   ```powershell
   python -m http.server 8080
   ```

---

## 📡 ESP32 Firmware Setup

1. Open [`firmware/esp32_motion_sensor.ino`](file:///c:/Users/kkabh/OneDrive/Documents/IOT%20PROJECT/Smart%20Home%20Security%20System/firmware/esp32_motion_sensor.ino) in the **Arduino IDE**.
2. Select your board: **Tools > Board > ESP32 Arduino > ESP32 Dev Module**.
3. Update the Wi-Fi credentials:
   ```cpp
   const char* WIFI_SSID     = "Your_WiFi_Network";
   const char* WIFI_PASSWORD = "Your_WiFi_Password";
   ```
4. Set the backend URL to your laptop's local IP:
   ```cpp
   // Find your PC IP with 'ipconfig' (e.g. 192.168.1.50)
   const char* BACKEND_URL = "http://192.168.1.50:5000/api/motion";
   ```
5. Click **Upload**. Open the Serial Monitor at `115200 baud` to observe bootup, calibration, and live trigger transmissions.

---

## 🌐 API Endpoints Reference

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | No | Returns backend status and database connection (`PostgreSQL` or `SQLite`). |
| `GET` | `/api/status` | No | Returns current motion state, online/offline status, and total event count. |
| `GET` | `/api/events?limit=8` | No | Returns list of recent timestamped motion events for the activity table. |
| `POST` | `/api/motion` | Yes (`X-API-Key`) | Ingests motion event or heartbeat from ESP32. (Simulation bypasses auth with `is_simulated: true`). |
| `POST` | `/api/events/clear` | No | Clears test event history for clean test runs. |

### Example Ingest Payload (`POST /api/motion`)
```json
{
  "device_id": "esp32-pir-01",
  "state": "MOTION_DETECTED",
  "gpio_pin": 27,
  "is_simulated": false,
  "details": "Infrared disturbance detected by HC-SR501"
}
```

---

## 🧪 Automated Test Suite & Verification Results

The automated test suite in [`backend/test_api.py`](file:///c:/Users/kkabh/OneDrive/Documents/IOT%20PROJECT/Smart%20Home%20Security%20System/backend/test_api.py) tests all core business logic:

```powershell
python -m pytest backend/test_api.py -v
```

### Actual Test Execution Results
- `test_health_check` — **PASSED** (200 OK, database connected)
- `test_authentication_failure` — **PASSED** (401 Unauthorized on missing/invalid API key)
- `test_valid_motion_ingest_with_auth` — **PASSED** (201 Created on valid trigger)
- `test_duplicate_reading_suppression` — **PASSED** (avoids database spam; preserves state)
- `test_motion_cleared_transition` — **PASSED** (201 Created on state clear)
- `test_status_endpoint` — **PASSED** (returns current state and counts)
- `test_events_list_endpoint` — **PASSED** (descending timestamp order)
- `test_simulated_dashboard_event` — **PASSED** (records simulation events)
- `test_invalid_payload` — **PASSED** (400 Bad Request on illegal state)
- **Container Persistence Test** — **PASSED** (Data survived a `docker compose restart`)

---

## ☁️ Free-Tier Cloud Deployment Guide

If you wish to deploy the system online for demonstration to your professors:

### Recommended Free-Tier Architecture
1. **Frontend:** **GitHub Pages** or **Vercel** (100% free static hosting with HTTPS).
2. **Backend API:** **Render.com** (Free Web Service tier, 750 free hours/month, automatic HTTPS).
3. **Database:** **Neon.tech** or **Supabase** (Free serverless PostgreSQL with 500MB storage, connection pooling, and zero cost).

### Deployment Steps:
1. Create a free account at [Neon.tech](https://neon.tech) and copy your PostgreSQL connection string.
2. Create a free Web Service on [Render.com](https://render.com) pointing to this repository (`backend/` folder).
3. Set the Environment Variables on Render:
   - `DATABASE_URL` = `<your-neon-postgres-connection-string>`
   - `ESP32_API_KEY` = `<strong-secret-key>`
   - `CORS_ORIGINS` = `*`
4. Deploy the frontend to GitHub Pages:
   - In [`js/script.js`](file:///c:/Users/kkabh/OneDrive/Documents/IOT%20PROJECT/Smart%20Home%20Security%20System/js/script.js), update `API_BASE_URL` to point to your live Render URL (`https://your-app.onrender.com/api`).
5. In the ESP32 code, set `BACKEND_URL` to your live Render endpoint.

> **Free-Tier Sleep Caveat:** Free web services on Render spin down after 15 minutes of inactivity. When the ESP32 or a user sends the first request after idle, the first response may take ~30-50 seconds to wake up the server.

---

## 🎓 College Assignment Report Outline

Use this structured outline for your final project report or presentation slides:

1. **Title Page:** Project Title, Student Name, Roll Number, Department, Guide Name, College Name.
2. **Abstract:** High-level summary of the IoT motion monitoring system, ESP32 hardware, and web dashboard.
3. **Introduction & Objectives:**
   - Problem statement (home intrusion detection, elderly care motion monitoring).
   - Objectives (low-cost IoT architecture, real-time web telemetry, database audit trail).
4. **Hardware Components & Specifications:**
   - ESP32-WROOM-32 (Dual-core 240MHz, Wi-Fi 802.11 b/g/n).
   - HC-SR501 Passive Infrared (PIR) Sensor (operating principles, 120° cone, 3.3V logic).
   - Circuit schematic and pin wiring diagram.
5. **Software Architecture & Methodology:**
   - Microcontroller firmware: interrupt debouncing, Wi-Fi reconnection, HTTP client, heartbeat intervals.
   - Backend architecture: Python Flask REST API, authentication middleware, state-transition filtering.
   - Database design: Device state table vs. historical event log table (PostgreSQL / SQLite).
   - Frontend interface: Clean semantic HTML5, CSS design tokens, asynchronous polling.
6. **Implementation Details:**
   - Step-by-step implementation of Docker containerization.
   - Dual-database fallback design.
7. **Testing & Results:**
   - Automated pytest test suite results.
   - Live hardware and simulated trigger validation.
   - Database persistence verification across container restarts.
8. **Limitations & Future Scope:**
   - Current limitations (PIR sensitivity to ambient heat gradients, local Wi-Fi dependencies).
   - Future enhancements (WebSocket streaming, camera module integration like ESP32-CAM, SMS/Telegram alert push notifications).
9. **Conclusion:** Summary of deliverables and learning outcomes.
10. **References:** Espressif ESP32 documentation, Flask framework documentation, PostgreSQL manual.
