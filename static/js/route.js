/* route.js — plan_route page map interactions */

let routeMap, originMarker, destMarker, routeLayer;

function initRouteMap(geojsonPoints, origin, dest) {
  const center = origin || window._MAP_CENTER || [28.6304, 77.2177];
  const zoom   = window._MAP_ZOOM || 15;

  routeMap = L.map('map').setView(center, zoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(routeMap);

  // Place markers if we have route data from server
  if (origin) {
    originMarker = L.marker(origin, { title: 'Origin' })
      .addTo(routeMap)
      .bindPopup('<b>📍 Origin</b>');
    setLatLngFields('origin', origin[0], origin[1]);
  }
  if (dest) {
    destMarker = L.marker(dest, {
      title: 'Destination',
      icon: L.icon({
        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
        iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34],
        shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
        shadowSize: [41, 41],
      }),
    })
      .addTo(routeMap)
      .bindPopup('<b>🏁 Destination</b>');
    setLatLngFields('dest', dest[0], dest[1]);
  }

  // Draw route line
  if (geojsonPoints && geojsonPoints.length > 1) {
    routeLayer = L.polyline(geojsonPoints, {
      color: '#27ae60', weight: 5, opacity: .85, dashArray: null,
    }).addTo(routeMap);
    routeMap.fitBounds(routeLayer.getBounds(), { padding: [24, 24] });
  }

  // Click-to-set
  routeMap.on('click', function (e) {
    const { lat, lng } = e.latlng;
    if (!originMarker) {
      originMarker = L.marker([lat, lng], { title: 'Origin' })
        .addTo(routeMap).bindPopup('<b>📍 Origin</b>').openPopup();
      setLatLngFields('origin', lat, lng);
      showToast('Origin set. Now click your destination.', 'info');
    } else if (!destMarker) {
      destMarker = L.marker([lat, lng], {
        title: 'Destination',
        icon: L.icon({
          iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
          iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34],
          shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
          shadowSize: [41, 41],
        }),
      }).addTo(routeMap).bindPopup('<b>🏁 Destination</b>').openPopup();
      setLatLngFields('dest', lat, lng);
      showToast('Destination set. Click "Calculate Route" to proceed.', 'success');
    } else {
      showToast('Both points already set. Reset to change them.', 'warning');
    }
  });
}

function setLatLngFields(prefix, lat, lng) {
  document.getElementById(`${prefix}_lat`).value = lat;
  document.getElementById(`${prefix}_lng`).value = lng;
}

function resetMarkers() {
  if (originMarker) { routeMap.removeLayer(originMarker); originMarker = null; }
  if (destMarker)   { routeMap.removeLayer(destMarker);   destMarker   = null; }
  if (routeLayer)   { routeMap.removeLayer(routeLayer);   routeLayer   = null; }
  ['origin_lat', 'origin_lng', 'dest_lat', 'dest_lng'].forEach(id => {
    document.getElementById(id).value = '';
  });
  showToast('Markers reset. Click map to set origin.', 'info');
}

// Validate form before submit
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('route-form');
  if (!form) return;

  form.addEventListener('submit', (e) => {
    const oLat = document.getElementById('origin_lat').value;
    const dLat = document.getElementById('dest_lat').value;
    if (!oLat || !dLat) {
      e.preventDefault();
      showToast('Please set both origin and destination on the map.', 'danger');
      return;
    }
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Calculating…';
  });
});
