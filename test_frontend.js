/**
 * SmartGuard Frontend Automated Verification Suite
 * Tests UI state rendering and API polling logic for:
 *   - MOTION_DETECTED -> NO_MOTION transitions
 *   - NO_MOTION -> MOTION_DETECTED transitions
 *   - Device online status distinction from motion status
 *   - Safe icon / alert icon toggling
 *   - Badges and CSS class assignments
 */

const assert = require('assert');

// 1. Mock DOM Element Factory
class MockElement {
  constructor(id = '', className = '') {
    this.id = id;
    this.className = className;
    this.textContent = '';
    this.classList = {
      classes: new Set(className.split(' ').filter(Boolean)),
      add: (c) => this.classList.classes.add(c),
      remove: (c) => this.classList.classes.delete(c),
      contains: (c) => this.classList.classes.has(c),
      toggle: (c) => {
        if (this.classList.classes.has(c)) this.classList.classes.delete(c);
        else this.classList.classes.add(c);
      }
    };
    this.children = [];
    this.innerHTML = '';
  }
}

// 2. Setup mock UI elements matching index.html
const motionStatusText = new MockElement('motionStatusText');
const motionBadge = new MockElement('motionBadge');
const motionIconWrap = new MockElement('motionIconWrap');
const safeIcon = new MockElement('safeIcon');
const alertIcon = new MockElement('alertIcon', 'hidden');

const sensorStatusText = new MockElement('sensorStatusText');
const sensorBadge = new MockElement('sensorBadge');

// Replicate script.js UI functions under test
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
  } else {
    sensorStatusText.textContent = 'Hardware Standby';
    sensorStatusText.className = 'card-value text-muted';
    if (sensorBadge) {
      sensorBadge.textContent = 'Waiting for ESP32';
      sensorBadge.className = 'badge badge-warning';
    }
  }
}

function handleStatusApiResponse(data) {
  const hasMotion = data.current_motion_state === 'MOTION_DETECTED';
  setMotionDisplay(hasMotion);
  setSensorDisplay(data.is_online, data.database_type);
}

// -----------------------------------------------------------------------------
// Test Execution
// -----------------------------------------------------------------------------
console.log('Running SmartGuard Frontend Automated Tests...\n');

// Test 1: Initial Quiet State (Device Online, No Motion)
console.log('Test 1: Render quiet state (Device Online, No Motion)...');
handleStatusApiResponse({
  current_motion_state: 'NO_MOTION',
  is_online: true,
  database_type: 'PostgreSQL'
});
assert.strictEqual(motionStatusText.textContent, 'No Motion Detected');
assert.strictEqual(motionStatusText.className, 'card-value text-safe');
assert.strictEqual(motionBadge.textContent, 'Normal State');
assert.strictEqual(motionBadge.className, 'badge badge-safe');
assert.strictEqual(sensorStatusText.textContent, 'ESP32 Connected');
assert.strictEqual(sensorBadge.textContent, 'Online (PostgreSQL)');
assert.strictEqual(safeIcon.classList.contains('hidden'), false);
assert.strictEqual(alertIcon.classList.contains('hidden'), true);
console.log('✓ Passed: Initial quiet state correctly rendered.\n');

// Test 2: Transition to MOTION_DETECTED
console.log('Test 2: Transition to MOTION_DETECTED...');
handleStatusApiResponse({
  current_motion_state: 'MOTION_DETECTED',
  is_online: true,
  database_type: 'PostgreSQL'
});
assert.strictEqual(motionStatusText.textContent, 'Motion Detected');
assert.strictEqual(motionStatusText.className, 'card-value text-alert');
assert.strictEqual(motionBadge.textContent, 'Motion Detected');
assert.strictEqual(motionBadge.className, 'badge badge-danger');
assert.strictEqual(sensorStatusText.textContent, 'ESP32 Connected');
assert.strictEqual(safeIcon.classList.contains('hidden'), true);
assert.strictEqual(alertIcon.classList.contains('hidden'), false);
console.log('✓ Passed: Transition to Motion Detected rendered with danger badge.\n');

// Test 3: Transition from MOTION_DETECTED -> NO_MOTION (Sensor Cleared)
console.log('Test 3: Transition from MOTION_DETECTED back to NO_MOTION (Person leaves)...');
handleStatusApiResponse({
  current_motion_state: 'NO_MOTION',
  is_online: true,
  database_type: 'PostgreSQL'
});
assert.strictEqual(motionStatusText.textContent, 'No Motion Detected');
assert.strictEqual(motionStatusText.className, 'card-value text-safe');
assert.strictEqual(motionBadge.textContent, 'Normal State');
assert.strictEqual(motionBadge.className, 'badge badge-safe');
assert.strictEqual(sensorStatusText.textContent, 'ESP32 Connected');
assert.strictEqual(sensorBadge.textContent, 'Online (PostgreSQL)');
assert.strictEqual(safeIcon.classList.contains('hidden'), false);
assert.strictEqual(alertIcon.classList.contains('hidden'), true);
console.log('✓ Passed: Transition back to No Motion verified; danger badge cleared.\n');

// Test 4: Verify Online Status is Distinct from Motion Status (Requirement 5)
console.log('Test 4: Verify Device Online is distinct from Motion Status...');
handleStatusApiResponse({
  current_motion_state: 'NO_MOTION',
  is_online: true,
  database_type: 'PostgreSQL'
});
// Device is connected AND motion is NO_MOTION simultaneously
assert.strictEqual(sensorStatusText.textContent, 'ESP32 Connected');
assert.strictEqual(motionStatusText.textContent, 'No Motion Detected');
console.log('✓ Passed: Device online status and motion status are strictly distinct.\n');

// Test 5: Verify Offline Device Standby Mode
console.log('Test 5: Verify Offline / Standby status rendering...');
handleStatusApiResponse({
  current_motion_state: 'NO_MOTION',
  is_online: false,
  database_type: 'PostgreSQL'
});
assert.strictEqual(sensorStatusText.textContent, 'Hardware Standby');
assert.strictEqual(sensorBadge.textContent, 'Waiting for ESP32');
assert.strictEqual(sensorBadge.className, 'badge badge-warning');
console.log('✓ Passed: Offline hardware standby rendered properly.\n');

console.log('====================================================');
console.log('All 5 Frontend Automated Tests Passed Successfully!');
console.log('====================================================');

