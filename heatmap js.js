let heatmap;
fetch('/api/heatmap_data')
  .then(r => r.json())
  .then(points => {
      heatmap = L.heatLayer(points, {radius: 25, blur: 15, maxZoom: 10}).addTo(map);
  });