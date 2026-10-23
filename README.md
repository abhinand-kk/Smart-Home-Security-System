# Smart Home Motion Monitoring System

A simple, clean, and responsive website for a college IoT project.

## 📋 Project Description
This project is an IoT-based home security system that uses an **ESP32 microcontroller** and a **PIR motion sensor (HC-SR501)** to detect movement inside a home. In the future, the sensor data will be sent to a Python backend and displayed live on this website.

Currently, the website is running in **Demonstration Mode** with sample data and interactive simulation buttons while hardware integration is being prepared.

---

## 🌟 Features & Sections

1. **Navigation Bar:**
   - Brand name: **Smart Home Monitor**
   - Quick links to **Home**, **Live Monitoring**, and **About**
   - Mobile-responsive navigation menu
2. **Home Section:**
   - Clear introduction and heading
   - "View Monitoring" button that smoothly scrolls to the live cards
3. **Live Monitoring Section:**
   - **Motion Status Card:** Displays *No Motion Detected* (Normal) or *Motion Detected* (Alert)
   - **Sensor Status Card:** Displays *Not Connected* (Demo Mode)
   - "Demo Mode — Hardware connection pending" note
   - **Simulate Motion** button: Changes status to *Motion Detected* and adds an event to the activity table
   - **Reset Status** button: Restores status back to *No Motion Detected*
4. **Recent Activity Section:**
   - Clean, readable table displaying sample motion events with date, time, and status badges
   - Dynamically updates when simulation buttons are clicked
5. **About Section:**
   - Explains the **ESP32 microcontroller**
   - Explains the **PIR motion sensor**
   - Details the planned **Python backend** (Flask)
   - Details the planned **Database** (SQLite) for storing motion logs
6. **Footer:**
   - Displays project name and college IoT project credentials

---

## 💻 How to Open and Run

### Method 1: Direct in Web Browser (Easiest)
Double-click `index.html` or drag it into any web browser (Google Chrome, Microsoft Edge, Firefox, Safari).

### Method 2: Local Python Server (Recommended)
Open a terminal or PowerShell in this project folder and run:
```bash
python -m http.server 8080
```
Then open your browser and navigate to:
```
http://localhost:8080
```

---

## 📁 File Structure
```
Smart Home Security System/
├── index.html       # Clean HTML5 structure for all sections
├── css/
│   └── style.css    # Clean CSS styling with white background & light blue accents
├── js/
│   └── script.js    # Beginner-friendly JavaScript for interactions and simulations
└── README.md        # Project guide and instructions
```

---

## 🔌 Future Phase: Connecting Hardware (ESP32 + Python Flask)
1. **Connect the PIR Sensor to ESP32:**
   - `VCC` -> `5V / VIN`
   - `GND` -> `GND`
   - `OUT` -> `GPIO 27` (or preferred digital input pin)
2. **Python Flask Server:**
   - Set up an endpoint `POST /api/motion` to receive alerts from the ESP32.
   - Set up `GET /api/status` for the website to fetch real-time motion and sensor states.
3. **Website Integration:**
   - Replace the simulation button trigger in `js/script.js` with an automated `fetch('/api/status')` call every 2 seconds.
