/* heatmap.js — community safety heatmap page */

document.addEventListener('DOMContentLoaded', () => {
  const center = window._MAP_CENTER || [28.6304, 77.2177];
  const zoom   = window._MAP_ZOOM   || 15;

  const map = L.map('heatMap').setView(center, zoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);

  const statusEl = document.getElementById('heatmap-status');

  fetch('/api/heatmap_data')
    .then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(points => {
      if (statusEl) statusEl.remove();
      if (!points.length) {
        showToast('No incident reports yet. Be the first to report!', 'info');
        return;
      }
      L.heatLayer(points, {
        radius:  28,
        blur:    18,
        maxZoom: 13,
        gradient: { 0.2: '#27ae60', 0.5: '#f39c12', 0.8: '#e74c3c', 1.0: '#7b241c' },
      }).addTo(map);

      // Optional: point count badge
      const badge = document.getElementById('report-count');
      if (badge) badge.textContent = points.length;
    })
    .catch(err => {
      console.error('Heatmap fetch failed:', err);
      if (statusEl) statusEl.textContent = 'Failed to load heatmap data.';
    });
});
