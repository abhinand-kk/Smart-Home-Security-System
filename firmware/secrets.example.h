#ifndef SECRETS_EXAMPLE_H
#define SECRETS_EXAMPLE_H

// =============================================================================
// SmartGuard ESP32 — Credentials Template
// Instructions:
//   1. Copy this file to "secrets.h" in the same directory:
//        cp firmware/secrets.example.h firmware/secrets.h
//   2. Fill in your real Wi-Fi SSID, password, and rotated API key.
//   3. "secrets.h" is ignored by git and will NEVER be committed.
// =============================================================================

// Wi-Fi Hotspot / Router Credentials
#define WIFI_SSID     "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// Central Backend Endpoint (Render Cloud API)
#define BACKEND_URL   "https://smartguard-api-c01f.onrender.com/api/motion"

// Physical Device Identifier & Secret API Key
// MUST match the ESP32_API_KEY environment variable configured on Render / .env
#define DEVICE_ID     "esp32-pir-01"
#define API_KEY       "YOUR_NEW_ROTATED_ESP32_API_KEY"

#endif // SECRETS_EXAMPLE_H

