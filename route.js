let map, originMarker, destMarker;
function initRouteMap(geojson, origin, dest) {
    map = L.map('map').setView([28.6304, 77.2177], 15);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    map.on('click', function(e) {
        if (!originMarker) {
            originMarker = L.marker(e.latlng).addTo(map).bindPopup('Origin').openPopup();
            document.getElementById('origin_lat').value = e.latlng.lat;
            document.getElementById('origin_lng').value = e.latlng.lng;
        } else if (!destMarker) {
            destMarker = L.marker(e.latlng).addTo(map).bindPopup('Destination').openPopup();
            document.getElementById('dest_lat').value = e.latlng.lat;
            document.getElementById('dest_lng').value = e.latlng.lng;
        }
    });
    if (geojson) {
        L.polyline(geojson, {color: 'green', weight: 5}).addTo(map);
        if (origin) map.setView(origin, 15);
    }
}