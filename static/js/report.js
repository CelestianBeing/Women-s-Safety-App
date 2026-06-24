/* report.js — incident report page */

document.addEventListener('DOMContentLoaded', () => {
  const center = window._MAP_CENTER || [28.6304, 77.2177];
  const zoom   = window._MAP_ZOOM   || 15;

  const reportMap = L.map('reportMap').setView(center, zoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(reportMap);

  let pin = null;
  let selectedLatLng = null;

  reportMap.on('click', (e) => {
    selectedLatLng = e.latlng;
    document.getElementById('lat').value = e.latlng.lat.toFixed(6);
    document.getElementById('lng').value = e.latlng.lng.toFixed(6);

    if (pin) reportMap.removeLayer(pin);
    pin = L.marker(e.latlng).addTo(reportMap)
      .bindPopup('📍 Incident location').openPopup();

    document.getElementById('location-hint').textContent =
      `Selected: ${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)}`;
  });

  // Use device location as default
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(pos => {
      reportMap.setView([pos.coords.latitude, pos.coords.longitude], zoom);
    });
  }

  // Form submit
  const form = document.getElementById('reportForm');
  const submitBtn = document.getElementById('submitBtn');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!selectedLatLng) {
      showToast('Please click on the map to mark the incident location.', 'danger');
      return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Submitting…';

    try {
      const res = await fetch('/api/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lat:         selectedLatLng.lat,
          lng:         selectedLatLng.lng,
          type:        document.getElementById('reportType').value,
          severity:    parseInt(document.getElementById('severity').value),
          description: document.getElementById('desc').value.trim(),
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        showToast('✅ Report submitted. Thank you for keeping the community safe!', 'success');
        form.reset();
        if (pin) { reportMap.removeLayer(pin); pin = null; }
        selectedLatLng = null;
        document.getElementById('location-hint').textContent = 'Click the map to select location';
      } else {
        showToast(data.message || 'Submission failed.', 'danger');
      }
    } catch {
      showToast('Network error. Please try again.', 'danger');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Submit Report';
    }
  });
});
