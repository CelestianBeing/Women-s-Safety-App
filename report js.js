let reportMap = L.map('reportMap').setView([28.6304, 77.2177], 15);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(reportMap);
let selectedLatLng;
reportMap.on('click', function(e) {
    selectedLatLng = e.latlng;
    document.getElementById('lat').value = e.latlng.lat;
    document.getElementById('lng').value = e.latlng.lng;
});
document.getElementById('reportForm').onsubmit = function(e) {
    e.preventDefault();
    fetch('/api/report', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            lat: selectedLatLng.lat,
            lng: selectedLatLng.lng,
            type: document.getElementById('reportType').value,
            severity: document.getElementById('severity').value,
            description: document.getElementById('desc').value
        })
    }).then(r => r.json()).then(res => alert('Report submitted!'));
};