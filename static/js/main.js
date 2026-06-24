/* main.js — global utilities */

// ── Mobile nav toggle ────────────────────────────────────────────────────────
const navToggle = document.getElementById('navToggle');
const navLinks  = document.getElementById('navLinks');
if (navToggle) {
  navToggle.addEventListener('click', () => navLinks.classList.toggle('open'));
}

// ── SOS modal ────────────────────────────────────────────────────────────────
function triggerSOS() {
  document.getElementById('sos-modal').classList.remove('hidden');
}
function closeModal() {
  document.getElementById('sos-modal').classList.add('hidden');
}
async function confirmSOS() {
  const btn = document.querySelector('#sos-modal .btn-danger');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Sending…';

  try {
    const res  = await fetch('/api/sos', { method: 'POST' });
    const data = await res.json();
    closeModal();
    showToast(data.message || 'SOS sent!', 'success');
  } catch {
    showToast('SOS failed — check your network.', 'danger');
    btn.disabled = false;
    btn.textContent = 'Yes, send SOS';
  }
}

// ── Toast notifications ──────────────────────────────────────────────────────
function showToast(msg, type = 'info', duration = 4000) {
  const container = getOrCreateToastContainer();
  const el = document.createElement('div');
  el.className = `flash flash-${type}`;
  el.style.cssText = 'animation: fadeIn .3s ease';
  el.innerHTML = `${msg} <button class="flash-close" onclick="this.parentElement.remove()">×</button>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), duration);
}
function getOrCreateToastContainer() {
  let c = document.getElementById('toast-container');
  if (!c) {
    c = document.createElement('div');
    c.id = 'toast-container';
    c.style.cssText = 'position:fixed;top:72px;right:16px;z-index:3000;width:320px;';
    document.body.appendChild(c);
  }
  return c;
}

// ── Location tracking (passive, best-effort) ─────────────────────────────────
let _locationInterval = null;

function startLocationTracking(routeNodes = []) {
  if (!navigator.geolocation) return;
  const send = (pos) => {
    fetch('/api/update_location', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lat:         pos.coords.latitude,
        lng:         pos.coords.longitude,
        route_nodes: routeNodes,
      }),
    }).catch(() => {});
  };
  navigator.geolocation.getCurrentPosition(send, () => {});
  _locationInterval = setInterval(() => {
    navigator.geolocation.getCurrentPosition(send, () => {});
  }, 30_000);
}

function stopLocationTracking() {
  if (_locationInterval) { clearInterval(_locationInterval); _locationInterval = null; }
}

// ── Safety score colour helper ────────────────────────────────────────────────
function safetyClass(score) {
  if (score >= 65) return 'score-high';
  if (score >= 40) return 'score-medium';
  return 'score-low';
}
function safetyLabel(score) {
  if (score >= 65) return '✅ Good';
  if (score >= 40) return '⚠️ Moderate';
  return '🚨 Low';
}
