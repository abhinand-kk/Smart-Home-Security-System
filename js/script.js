/**
 * Smart Home Motion Monitoring System
 * Simple & Beginner-Friendly JavaScript
 */

document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  // -------------------------------------------------------------------------
  // 1. DOM Elements
  // -------------------------------------------------------------------------
  const navToggle = document.getElementById('navToggle');
  const navMenu = document.getElementById('navMenu');
  const navLinks = document.querySelectorAll('.nav-link');
  
  // Status Card Elements
  const motionStatusText = document.getElementById('motionStatusText');
  const motionBadge = document.getElementById('motionBadge');
  const motionIconWrap = document.getElementById('motionIconWrap');
  const safeIcon = document.getElementById('safeIcon');
  const alertIcon = document.getElementById('alertIcon');

  // Control Buttons
  const simulateMotionBtn = document.getElementById('simulateMotionBtn');
  const resetMotionBtn = document.getElementById('resetMotionBtn');
  const activityTableBody = document.getElementById('activityTableBody');

  // -------------------------------------------------------------------------
  // 2. Mobile Navigation Toggle
  // -------------------------------------------------------------------------
  if (navToggle && navMenu) {
    navToggle.addEventListener('click', function () {
      navMenu.classList.toggle('open');
    });

    // Close menu when a link is clicked
    navLinks.forEach(function (link) {
      link.addEventListener('click', function () {
        navMenu.classList.remove('open');
      });
    });
  }

  // Active Link on Scroll
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
  // 3. Helper: Format Current Time (e.g. 11:45 AM)
  // -------------------------------------------------------------------------
  function getCurrentTimeString() {
    const now = new Date();
    let hours = now.getHours();
    const minutes = now.getMinutes();
    const ampm = hours >= 12 ? 'PM' : 'AM';

    hours = hours % 12;
    hours = hours ? hours : 12; // '0' should be '12'
    const formattedMinutes = minutes < 10 ? '0' + minutes : minutes;

    return hours + ':' + formattedMinutes + ' ' + ampm;
  }

  // -------------------------------------------------------------------------
  // 4. Add Simulated Event to Recent Activity Table
  // -------------------------------------------------------------------------
  function addActivityEvent(statusText, badgeClass) {
    if (!activityTableBody) return;

    const row = document.createElement('tr');
    const timeString = getCurrentTimeString();

    row.innerHTML = `
      <td>Today</td>
      <td>${timeString}</td>
      <td><span class="badge ${badgeClass}">${statusText}</span></td>
    `;

    // Insert at the very top of the table
    activityTableBody.insertBefore(row, activityTableBody.firstChild);

    // Keep table to at most 8 rows for a clean presentation
    if (activityTableBody.children.length > 8) {
      activityTableBody.removeChild(activityTableBody.lastChild);
    }
  }

  // -------------------------------------------------------------------------
  // 5. Simulate Motion Detected Button
  // -------------------------------------------------------------------------
  if (simulateMotionBtn) {
    simulateMotionBtn.addEventListener('click', function () {
      // Update text to "Motion Detected"
      motionStatusText.textContent = 'Motion Detected';
      motionStatusText.className = 'card-value text-alert';

      // Update badge
      motionBadge.textContent = 'Motion Detected';
      motionBadge.className = 'badge badge-danger';

      // Update icon container and icons
      motionIconWrap.className = 'card-icon-wrap alert';
      safeIcon.classList.add('hidden');
      alertIcon.classList.remove('hidden');

      // Add to demonstration activity table
      addActivityEvent('Motion Detected', 'badge-danger');
    });
  }

  // -------------------------------------------------------------------------
  // 6. Reset Status Button
  // -------------------------------------------------------------------------
  if (resetMotionBtn) {
    resetMotionBtn.addEventListener('click', function () {
      // Update text back to "No Motion Detected"
      motionStatusText.textContent = 'No Motion Detected';
      motionStatusText.className = 'card-value text-safe';

      // Update badge
      motionBadge.textContent = 'Normal State';
      motionBadge.className = 'badge badge-safe';

      // Update icon container and icons
      motionIconWrap.className = 'card-icon-wrap';
      safeIcon.classList.remove('hidden');
      alertIcon.classList.add('hidden');

      // Add to demonstration activity table
      addActivityEvent('No Motion', 'badge-safe');
    });
  }

  console.log('Smart Home Motion Monitoring System website initialized in demo mode.');
});
