/**
 * Smart Home Motion Monitoring System
 * Live API Connected & Responsive Client Script
 * 
 * Connects to Python Flask backend (/api/status, /api/events, /api/motion)
 * with graceful offline fallback, cloud hosting support, and simulation capabilities.
 */

document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  // -------------------------------------------------------------------------
  // 1. API Configuration & Cloud Detection
  // -------------------------------------------------------------------------
  function resolveApiUrl() {
    const custom = localStorage.getItem('smartguard_api_url');
    if (custom) return custom.replace(/\/+$/, '');

    // If served over HTTPS (e.g. Vercel deployment), prevent mixed-content blocking
    if (window.location.protocol === 'https:') {
      return '/api';
    }

    // Default to local Flask backend when running locally on HTTP / localhost
    return 'http://localhost:5000/api';
  }

  const API_BASE_URL = resolveApiUrl();
  const POLLING_INTERVAL_MS = 2000; // Poll every 2 seconds

  let isBackendConnected = false;
  let pollingTimer = null;

  // -------------------------------------------------------------------------
  // 2. DOM Elements Cache
  // -------------------------------------------------------------------------
  const navToggle = document.getElementById('navToggle');
  const navMenu = document.getElementById('navMenu');
  const navLinks = document.querySelectorAll('.nav-link');
  
  // Status Card Elements
  const motionCard = document.getElementById('motionCard');
  const motionStatusText = document.getElementById('motionStatusText');
  const motionBadge = document.getElementById('motionBadge');
  const motionIconWrap = document.getElementById('motionIconWrap');
  const safeIcon = document.getElementById('safeIcon');
  const alertIcon = document.getElementById('alertIcon');

  const sensorStatusText = document.getElementById('sensorStatusText');
  const sensorBadge = document.querySelector('.card:nth-child(2) .badge') || document.getElementById('sensorBadge');
  const demoBanner = document.querySelector('.demo-banner');

  // Control Buttons
  const simulateMotionBtn = document.getElementById('simulateMotionBtn');
  const resetMotionBtn = document.getElementById('resetMotionBtn');
  const activityTableBody = document.getElementById('activityTableBody');

  // -------------------------------------------------------------------------
  // 3. Mobile Navigation Toggle
  // -------------------------------------------------------------------------
  if (navToggle && navMenu) {
    navToggle.addEventListener('click', function () {
      navMenu.classList.toggle('open');
    });

    navLinks.forEach(function (link) {
      link.addEventListener('click', function () {
        navMenu.classList.remove('open');
      });
    });
  }

  // Active Link Tracking on Scroll
  window.addEventListener('scroll', function () {
    const sections = document.querySelectorAll('section');
    const scrollPos = window.scrollY + 100;

    sections.forEach(function (section) {
      const top = section.offsetTop;
      const height = section.offsetHeight;
      const id = section.getAttribute('id');

      if (scrollPos >= top && scrollPos < top + height) {
        navLinks.forEach(function (link) {
          link.classList.remove('active');
          if (link.getAttribute('href') === '#' + id) {
            link.classList.add('active');
          }
        });
      }
    });
  });

  // -------------------------------------------------------------------------
  // 4. Update UI Components based on State
  // -------------------------------------------------------------------------
  function setMotionDisplay(isMotion) {
    if (!motionStatusText || !motionBadge || !motionIconWrap) return;

    if (isMotion) {
      motionStatusText.textContent = 'Motion Detected';
      motionStatusText.className = 'card-value text-alert';

      motionBadge.textContent = 'Motion Detected';
      motionBadge.className = 'badge badge-danger';

      motionIconWrap.className = 'card-icon-wrap alert';
      if (safeIcon) safeIcon.classList.add('hidden');
      if (alertIcon) alertIcon.classList.remove('hidden');
    } else {
      motionStatusText.textContent = 'No Motion Detected';
      motionStatusText.className = 'card-value text-safe';

      motionBadge.textContent = 'Normal State';
      motionBadge.className = 'badge badge-safe';

      motionIconWrap.className = 'card-icon-wrap';
      if (safeIcon) safeIcon.classList.remove('hidden');
      if (alertIcon) alertIcon.classList.add('hidden');
    }
  }

  function setSensorDisplay(isOnline, dbType) {
    if (!sensorStatusText) return;

    if (isOnline) {
      sensorStatusText.textContent = 'ESP32 Connected';
      sensorStatusText.className = 'card-value text-safe';
      if (sensorBadge) {
        sensorBadge.textContent = `Online (${dbType || 'Postgres'})`;
        sensorBadge.className = 'badge badge-safe';
      }
      if (demoBanner) {
        demoBanner.innerHTML = `
          <span class="demo-dot" style="background-color: var(--color-safe);"></span>
          <span class="demo-text"><strong>Live System Active</strong> — ESP32 hardware streaming to Flask & ${dbType || 'Database'}</span>
        `;
      }
    } else {
      sensorStatusText.textContent = isBackendConnected ? 'Hardware Standby' : 'Backend Connecting...';
      sensorStatusText.className = 'card-value text-muted';
      if (sensorBadge) {
        sensorBadge.textContent = isBackendConnected ? 'Waiting for ESP32' : 'Local Demo Mode';
        sensorBadge.className = 'badge badge-warning';
      }
      if (demoBanner) {
        const isHttps = window.location.protocol === 'https:';
        const configPrompt = isHttps ? ` | <a href="#" id="setCloudApiBtn" style="color:inherit;text-decoration:underline;font-weight:600;">Configure Cloud API</a>` : '';
        demoBanner.innerHTML = `
          <span class="demo-dot"></span>
          <span class="demo-text"><strong>Demo Mode</strong> — Hardware connection pending. Testing enabled.${configPrompt}</span>
        `;
        
        const setCloudApiBtn = document.getElementById('setCloudApiBtn');
        if (setCloudApiBtn) {
          setCloudApiBtn.addEventListener('click', function (e) {
            e.preventDefault();
            const current = localStorage.getItem('smartguard_api_url') || '';
            const newUrl = prompt('Enter your deployed Flask backend API URL (e.g., https://your-backend.onrender.com/api):', current);
            if (newUrl !== null) {
              if (newUrl.trim() === '') {
                localStorage.removeItem('smartguard_api_url');
              } else {
                localStorage.setItem('smartguard_api_url', newUrl.trim());
              }
              window.location.reload();
            }
          });
        }
      }
    }
  }

  // -------------------------------------------------------------------------
  // 5. Render History Table from Live Database
  // -------------------------------------------------------------------------
  function renderEventsTable(events) {
    if (!activityTableBody || !Array.isArray(events)) return;

    if (events.length === 0) {
      activityTableBody.innerHTML = `
        <tr>
          <td colspan="3" style="text-align: center; color: var(--text-muted); padding: 20px;">
            No motion events recorded in the database yet.
          </td>
        </tr>
      `;
      return;
    }

    let html = '';
    events.slice(0, 8).forEach(function (ev) {
      const isMotion = ev.event_type === 'MOTION_DETECTED';
      const badgeClass = isMotion ? 'badge-danger' : 'badge-safe';
      const statusLabel = isMotion ? 'Motion Detected' : 'No Motion';
      const simTag = ev.is_simulated ? ' (Sim)' : '';

      html += `
        <tr>
          <td>${ev.formatted_date || 'Today'}</td>
          <td>${ev.formatted_time || 'Just now'}</td>
          <td><span class="badge ${badgeClass}">${statusLabel}${simTag}</span></td>
        </tr>
      `;
    });

    activityTableBody.innerHTML = html;
  }

  // -------------------------------------------------------------------------
  // 6. Polling: Fetch Live Status & Events from API
  // -------------------------------------------------------------------------
  async function fetchLiveStatus() {
    try {
      const response = await fetch(`${API_BASE_URL}/status`, {
        headers: { 'Accept': 'application/json' }
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      isBackendConnected = true;

      // Update Motion Status Card
      const hasMotion = data.current_motion_state === 'MOTION_DETECTED';
      setMotionDisplay(hasMotion);

      // Update Sensor Status Card
      setSensorDisplay(data.is_online, data.database_type);

    } catch (err) {
      // Backend unavailable or starting up -> fall back to graceful demo state
      isBackendConnected = false;
      setSensorDisplay(false, 'Local');
    }
  }

  async function fetchLiveEvents() {
    if (!isBackendConnected) return;

    try {
      const response = await fetch(`${API_BASE_URL}/events?limit=8`, {
        headers: { 'Accept': 'application/json' }
      });

      if (response.ok) {
        const data = await response.json();
        if (data.events && data.events.length > 0) {
          renderEventsTable(data.events);
        }
      }
    } catch (err) {
      // Non-critical; retain table as is
    }
  }

  // Synchronized Poll Cycle
  async function pollBackend() {
    await fetchLiveStatus();
    await fetchLiveEvents();
  }

  // -------------------------------------------------------------------------
  // 7. Interactive Simulation Actions (Post to Real Backend)
  // -------------------------------------------------------------------------
  async function sendSimulatedEvent(stateType) {
    const isMotion = stateType === 'MOTION_DETECTED';

    // Immediate UI responsiveness
    setMotionDisplay(isMotion);

    try {
      const response = await fetch(`${API_BASE_URL}/motion`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          device_id: 'dashboard-sim-01',
          state: stateType,
          gpio_pin: 27,
          is_simulated: true,
          details: `Simulated by dashboard user at ${new Date().toLocaleTimeString()}`
        })
      });

      if (response.ok) {
        // Refresh table immediately with new DB row
        fetchLiveEvents();
      } else {
        // Fallback local table row if backend returned error
        addLocalTableRow(stateType);
      }
    } catch (err) {
      // Fallback local table row if backend offline
      addLocalTableRow(stateType);
    }
  }

  function addLocalTableRow(stateType) {
    if (!activityTableBody) return;
    const isMotion = stateType === 'MOTION_DETECTED';
    const row = document.createElement('tr');
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    row.innerHTML = `
      <td>Today</td>
      <td>${timeStr}</td>
      <td><span class="badge ${isMotion ? 'badge-danger' : 'badge-safe'}">${isMotion ? 'Motion Detected (Sim)' : 'No Motion (Sim)'}</span></td>
    `;
    activityTableBody.insertBefore(row, activityTableBody.firstChild);
    if (activityTableBody.children.length > 8) {
      activityTableBody.removeChild(activityTableBody.lastChild);
    }
  }

  if (simulateMotionBtn) {
    simulateMotionBtn.addEventListener('click', function () {
      sendSimulatedEvent('MOTION_DETECTED');
    });
  }

  if (resetMotionBtn) {
    resetMotionBtn.addEventListener('click', function () {
      sendSimulatedEvent('NO_MOTION');
    });
  }

  // -------------------------------------------------------------------------
  // 8. Start Background Polling
  // -------------------------------------------------------------------------
  pollBackend();
  pollingTimer = setInterval(pollBackend, POLLING_INTERVAL_MS);

  console.log(`[SmartGuard] Initialized. Polling backend at ${API_BASE_URL} every ${POLLING_INTERVAL_MS / 1000}s`);
});
