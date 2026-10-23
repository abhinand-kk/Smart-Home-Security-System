/*
 * =============================================================================
 * SmartGuard — IoT Smart Home Motion Monitoring System
 * Production ESP32 Firmware with Flask API Client & Local Diagnostics
 * =============================================================================
 * Hardware:
 *   - ESP32-WROOM-32 Development Board
 *   - HC-SR501 Passive Infrared (PIR) Motion Sensor
 * 
 * Pinout Connections:
 *   - HC-SR501 VCC -> ESP32 VIN (5V)
 *   - HC-SR501 GND -> ESP32 GND
 *   - HC-SR501 OUT -> ESP32 GPIO 27 (Digital Input with internal pull-down)
 *   - On-board LED -> GPIO 2 (Visual status indicator: blinks on Wi-Fi, solid on motion)
 * =============================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <WebServer.h>

// -----------------------------------------------------------------------------
// 1. Wi-Fi & Central Backend Server Configuration
// -----------------------------------------------------------------------------
// Your phone hotspot SSID
const char* WIFI_SSID     = "POCO F6";

// >>> FILL IN YOUR HOTSPOT PASSWORD HERE <<<
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD_HERE";

// Central Python Flask Backend Endpoint
// Automatically set to your laptop's Wi-Fi IP (Port 5000) on the POCO F6 network.
// If your laptop's IP changes in the future, update the IP address below.
const char* BACKEND_URL = "http://192.168.60.143:5000/api/motion";

// Device Identifier & Secret API Key
// MUST match the ESP32_API_KEY defined in the backend .env file.
const char* DEVICE_ID = "esp32-pir-01";
const char* API_KEY   = "smartguard-esp32-secret-key-2026";

// -----------------------------------------------------------------------------
// 2. Hardware Pin Configuration & Timing Constants
// -----------------------------------------------------------------------------
const int PIR_PIN        = 27;   // HC-SR501 Digital Output Pin
const int STATUS_LED_PIN = 2;    // Built-in Blue LED (GPIO 2 on most ESP32 boards)

// Timing settings
const unsigned long DEBOUNCE_DELAY_MS     = 250;     // 250ms debouncing window
const unsigned long HEARTBEAT_INTERVAL_MS = 30000;   // 30s heartbeat ping when room is quiet
const unsigned long HTTP_TIMEOUT_MS       = 5000;    // 5-second timeout for server response
const int MAX_RETRY_ATTEMPTS              = 3;       // Maximum retries on transmission failure

// -----------------------------------------------------------------------------
// 3. Runtime State & Local Diagnostic Web Server
// -----------------------------------------------------------------------------
int lastStablePirState       = LOW;
int lastRawReading           = LOW;
unsigned long lastDebounceTime = 0;
unsigned long lastHeartbeatTime = 0;
unsigned long lastDebugPrintTime = 0;
int consecutiveFailures      = 0;
unsigned long totalMotionEventsSent = 0;

// Local web server on port 80 for on-board diagnostics
WebServer localServer(80);

// -----------------------------------------------------------------------------
// 4. Local Web Server Handlers (Preserves direct-to-ESP32 debugging)
// -----------------------------------------------------------------------------
void handleRoot() {
  String html = "<!DOCTYPE html><html><head><title>ESP32 Node Status</title>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1'>";
  html += "<style>body{font-family:sans-serif;margin:30px;line-height:1.6;color:#1e293b;background:#f8fafc;}";
  html += ".card{background:#fff;padding:20px;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.06);max-width:500px;}";
  html += ".badge{padding:4px 10px;border-radius:20px;font-weight:bold;color:#fff;}";
  html += ".badge-red{background:#dc2626;} .badge-green{background:#16a34a;}";
  html += "</style></head><body><div class='card'>";
  html += "<h2>SmartGuard ESP32 Sensor Node</h2>";
  html += "<p><strong>Device ID:</strong> " + String(DEVICE_ID) + "</p>";
  html += "<p><strong>PIR Pin:</strong> GPIO " + String(PIR_PIN) + "</p>";
  html += "<p><strong>Current Motion:</strong> ";
  if (digitalRead(PIR_PIN) == HIGH) {
    html += "<span class='badge badge-red'>MOTION DETECTED (HIGH)</span>";
  } else {
    html += "<span class='badge badge-green'>NO MOTION (LOW)</span>";
  }
  html += "</p>";
  html += "<p><strong>Backend Target:</strong> " + String(BACKEND_URL) + "</p>";
  html += "<p><strong>Events Dispatched:</strong> " + String(totalMotionEventsSent) + "</p>";
  html += "<p><small>JSON endpoint available at <a href='/api/status'>/api/status</a></small></p>";
  html += "</div></body></html>";
  localServer.send(200, "text/html", html);
}

void handleLocalStatusApi() {
  int rawReading = digitalRead(PIR_PIN);
  String json = "{";
  json += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
  json += "\"pir_gpio\":" + String(PIR_PIN) + ",";
  json += "\"pir_state\":" + String(rawReading) + ",";
  json += "\"motion_detected\":" + String(rawReading == HIGH ? "true" : "false") + ",";
  json += "\"events_sent\":" + String(totalMotionEventsSent) + ",";
  json += "\"wifi_rssi\":" + String(WiFi.RSSI()) + ",";
  json += "\"uptime_ms\":" + String(millis()) + ",";
  json += "\"target_backend\":\"" + String(BACKEND_URL) + "\"";
  json += "}";
  localServer.send(200, "application/json", json);
}

// -----------------------------------------------------------------------------
// 5. Wi-Fi Connection Helper
// -----------------------------------------------------------------------------
void connectToWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println();
  Serial.print("[WiFi] Connecting to hotspot: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN)); // Toggle LED
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(STATUS_LED_PIN, LOW);
    Serial.println();
    Serial.println("[WiFi] Connected successfully!");
    Serial.print("[WiFi] ESP32 Assigned IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("[WiFi] Signal RSSI: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
    Serial.println("[WiFi] Local Diagnostic page ready at: http://" + WiFi.localIP().toString() + "/");
  } else {
    Serial.println();
    Serial.println("[WiFi] Connection failed. Check password and verify hotspot is enabled.");
  }
}

// -----------------------------------------------------------------------------
// 6. Send Event to Central Flask API (POST /api/motion)
// -----------------------------------------------------------------------------
bool sendEventToBackend(const char* stateType, const char* details) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP] Wi-Fi lost. Attempting reconnection...");
    connectToWiFi();
    if (WiFi.status() != WL_CONNECTED) return false;
  }

  HTTPClient http;
  bool isHttps = (strncmp(BACKEND_URL, "https://", 8) == 0);

  if (isHttps) {
    WiFiClientSecure *client = new WiFiClientSecure;
    if (client) {
      client->setInsecure(); // Or client->setCACert(root_ca) for strict verification
      http.begin(*client, BACKEND_URL);
    } else {
      Serial.println("[HTTP] Secure client initialization failed");
      return false;
    }
  } else {
    http.begin(BACKEND_URL);
  }

  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");
  // Device authentication header (Kept secure; not printed to Serial)
  http.addHeader("X-API-Key", API_KEY);

  // Construct JSON payload matching the Flask backend schema
  String ipStr = WiFi.localIP().toString();
  String payload = "{";
  payload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
  payload += "\"state\":\"" + String(stateType) + "\",";
  payload += "\"gpio_pin\":" + String(PIR_PIN) + ",";
  payload += "\"is_simulated\":false,";
  payload += "\"ip_address\":\"" + ipStr + "\",";
  payload += "\"details\":\"" + String(details) + "\"";
  payload += "}";

  Serial.print("[HTTP] Dispatching payload to Flask (State: ");
  Serial.print(stateType);
  Serial.println(")...");

  int httpCode = -1;
  int retry = 0;

  while (retry < MAX_RETRY_ATTEMPTS) {
    httpCode = http.POST(payload);

    if (httpCode > 0) {
      Serial.print("[HTTP] Server responded with HTTP code: ");
      Serial.println(httpCode);

      if (httpCode == 200 || httpCode == 201) {
        String response = http.getString();
        Serial.print("[HTTP] Server Response: ");
        Serial.println(response);
        consecutiveFailures = 0;
        totalMotionEventsSent++;
        http.end();
        return true;
      }
    } else {
      Serial.print("[HTTP] POST attempt failed, error: ");
      Serial.println(http.errorToString(httpCode).c_str());
      retry++;
      delay(500 * retry); // Exponential backoff
    }
  }

  consecutiveFailures++;
  Serial.print("[HTTP] Warning: Transmission failed after ");
  Serial.print(MAX_RETRY_ATTEMPTS);
  Serial.println(" attempts. Will retry on next event.");
  http.end();
  return false;
}

// -----------------------------------------------------------------------------
// 7. Arduino Setup
// -----------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("======================================================");
  Serial.println("SmartGuard IoT Motion Sensor — ESP32 Client Firmware");
  Serial.println("======================================================");

  // Pin Configuration:
  // Use INPUT_PULLDOWN so GPIO 27 doesn't float when no sensor is connected
  pinMode(PIR_PIN, INPUT_PULLDOWN);
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);

  // Connect to Wi-Fi Hotspot
  connectToWiFi();

  // Setup local diagnostic web server routes
  localServer.on("/", handleRoot);
  localServer.on("/api/status", handleLocalStatusApi);
  localServer.begin();
  Serial.println("[HTTP] Local diagnostic server started on port 80.");

  // HC-SR501 PIR Sensor Warmup
  Serial.println("[PIR] Calibrating HC-SR501 PIR Sensor (~5 seconds)...");
  for (int i = 0; i < 5; i++) {
    digitalWrite(STATUS_LED_PIN, HIGH);
    delay(200);
    digitalWrite(STATUS_LED_PIN, LOW);
    delay(800);
    Serial.print(".");
  }
  Serial.println();
  Serial.println("[PIR] Calibration Complete. PIR Monitoring Active on GPIO 27!");

  // Dispatch initial startup heartbeat to register with Flask backend
  sendEventToBackend("HEARTBEAT", "ESP32 Sensor Node booted and calibrated");
  lastHeartbeatTime = millis();
}

// -----------------------------------------------------------------------------
// 8. Arduino Main Loop
// -----------------------------------------------------------------------------
void loop() {
  // Handle incoming HTTP requests on local diagnostic web server
  localServer.handleClient();

  // Ensure Wi-Fi stays connected
  if (WiFi.status() != WL_CONNECTED) {
    connectToWiFi();
  }

  int currentReading = digitalRead(PIR_PIN);

  // Debouncing logic to filter rapid contact bounce
  if (currentReading != lastRawReading) {
    lastDebounceTime = millis();
  }
  lastRawReading = currentReading;

  // Print raw sensor reading every 2 seconds for Serial Monitor debugging
  if (millis() - lastDebugPrintTime >= 2000) {
    Serial.print("[PIR Raw] GPIO 27 = ");
    Serial.print(currentReading == HIGH ? "HIGH (Motion)" : "LOW (Quiet)");
    Serial.print(" | Wi-Fi RSSI: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
    lastDebugPrintTime = millis();
  }

  // State Transition Detection (only fires when state changes)
  if ((millis() - lastDebounceTime) > DEBOUNCE_DELAY_MS) {
    if (currentReading != lastStablePirState) {
      lastStablePirState = currentReading;

      if (lastStablePirState == HIGH) {
        // State 1: Motion Detected
        Serial.println("\n>>> [EVENT] MOTION DETECTED! (GPIO 27 -> HIGH) <<<");
        digitalWrite(STATUS_LED_PIN, HIGH); // Turn LED ON
        sendEventToBackend("MOTION_DETECTED", "Infrared disturbance detected by HC-SR501");
      } else {
        // State 2: Motion Cleared / Standby
        Serial.println("\n--- [EVENT] MOTION CLEARED. (GPIO 27 -> LOW) ---");
        digitalWrite(STATUS_LED_PIN, LOW);  // Turn LED OFF
        sendEventToBackend("NO_MOTION", "Sensor returned to quiet state");
      }

      lastHeartbeatTime = millis(); // Reset heartbeat timer upon active transition
    }
  }

  // Periodic Heartbeat (dispatched every 30s when room is quiet)
  if (millis() - lastHeartbeatTime >= HEARTBEAT_INTERVAL_MS) {
    Serial.println("\n[HEARTBEAT] Sending periodic 30s keep-alive ping to Flask...");
    sendEventToBackend("HEARTBEAT", "Periodic sensor health keep-alive");
    lastHeartbeatTime = millis();
  }

  delay(20); // Small processing loop delay
}
