import networkx as nx
from safety_scoring import load_graph, get_edge_safety

def find_safest_route(G, orig_point, dest_point):
    """Find route maximizing safety using Dijkstra/A*."""
    # Get nearest nodes
    orig_node = ox.distance.nearest_nodes(G, X=orig_point[1], Y=orig_point[0])
    dest_node = ox.distance.nearest_nodes(G, X=dest_point[1], Y=dest_point[0])

    # Safety weight = 101 - safety_score (so higher safety = lower weight)
    def weight_function(u, v, key, data):
        safety, _ = get_edge_safety(u, v, key, G)
        # Add small distance component to avoid absurdly long safe detours
        length = data.get('length', 50)
        distance_weight = length * 0.1  # adjust bias
        return (101 - safety) * 10 + distance_weight  # safety dominates

    # Compute safest path
    try:
        safe_path = nx.shortest_path(G, orig_node, dest_node, weight=lambda u, v, d: weight_function(u, v, d['key'], d), method='dijkstra')
        # Gather details
        route_edges = []
        total_safety = 0
        total_distance = 0
        confidences = []
        for i in range(len(safe_path)-1):
            u, v = safe_path[i], safe_path[i+1]
            edge_data = G.get_edge_data(u, v)
            key = min(edge_data.keys())  # take first
            safety, conf = get_edge_safety(u, v, key, G)
            length = edge_data[key].get('length', 0)
            route_edges.append((u, v, safety, length, conf))
            total_safety += safety * length
            total_distance += length
            confidences.append(conf)
        avg_safety = total_safety / total_distance if total_distance else 0
        avg_confidence = sum(confidences)/len(confidences) if confidences else 0
        return {
            'path_nodes': safe_path,
            'route_edges': route_edges,
            'avg_safety': round(avg_safety, 1),
            'avg_confidence': round(avg_confidence, 1),
            'total_distance_m': round(total_distance, 0)
        }
    except nx.NetworkXNoPath:
        return None

def compute_route_geojson(G, path_nodes):
    """Convert node path to GeoJSON for Leaflet."""
    points = []
    for node in path_nodes:
        points.append([G.nodes[node]['y'], G.nodes[node]['x']])
    return points