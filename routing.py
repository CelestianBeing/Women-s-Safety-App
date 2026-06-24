"""
Safest-route computation using Dijkstra with a safety-weighted graph.
"""
import logging
import osmnx as ox
import networkx as nx

from safety_scoring import get_edge_safety

logger = logging.getLogger(__name__)


def find_safest_route(G: nx.MultiDiGraph, orig_point: tuple, dest_point: tuple) -> dict | None:
    """
    Find the route that maximises pedestrian safety between two lat/lng points.

    Args:
        G:           OSM walk graph
        orig_point:  (lat, lng)
        dest_point:  (lat, lng)

    Returns:
        dict with path_nodes, route_edges, avg_safety, avg_confidence,
        total_distance_m — or None if no path exists.
    """
    try:
        orig_node = ox.distance.nearest_nodes(G, X=orig_point[1],  Y=orig_point[0])
        dest_node = ox.distance.nearest_nodes(G, X=dest_point[1], Y=dest_point[0])
    except Exception as exc:
        logger.error("nearest_nodes failed: %s", exc)
        return None

    if orig_node == dest_node:
        return None

    def _weight(u: int, v: int, edge_dict: dict) -> float:
        """
        NetworkX passes the *first* edge dict for multi-edges.
        Safety score 1–99 → weight 99–1 (invert so shortest path = safest).
        Small distance component prevents absurdly long safe detours.
        """
        key = min(edge_dict.keys()) if isinstance(edge_dict, dict) else 0
        # edge_dict may be the raw data dict directly in some NX versions
        if isinstance(edge_dict, dict) and 'length' in edge_dict:
            data = edge_dict
        else:
            data = G.get_edge_data(u, v, key) or {}

        safety, _ = get_edge_safety(u, v, key, G)
        length     = data.get('length', 50)
        return (101 - safety) * 10 + length * 0.05

    try:
        path = nx.shortest_path(G, orig_node, dest_node, weight=_weight, method='dijkstra')
    except nx.NetworkXNoPath:
        logger.warning("No path from %s to %s", orig_node, dest_node)
        return None
    except nx.NodeNotFound as exc:
        logger.error("Node not found: %s", exc)
        return None

    # ── Collect edge-level details ────────────────────────────────────────
    route_edges    = []
    total_safety   = 0.0
    total_distance = 0.0
    confidences    = []

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        edge_data = G.get_edge_data(u, v)
        if not edge_data:
            continue
        key    = min(edge_data.keys())
        data   = edge_data[key]
        safety, conf = get_edge_safety(u, v, key, G)
        length = data.get('length', 0)

        route_edges.append({
            'u':      u,
            'v':      v,
            'safety': round(safety, 1),
            'length': round(length, 1),
            'conf':   round(conf, 1),
        })
        total_safety   += safety * length
        total_distance += length
        confidences.append(conf)

    if total_distance == 0:
        return None

    return {
        'path_nodes':       path,
        'route_edges':      route_edges,
        'avg_safety':       round(total_safety / total_distance, 1),
        'avg_confidence':   round(sum(confidences) / len(confidences), 1),
        'total_distance_m': round(total_distance, 0),
        'num_segments':     len(route_edges),
    }


def compute_route_geojson(G: nx.MultiDiGraph, path_nodes: list) -> list[list[float]]:
    """Convert a list of OSM node IDs to [[lat, lng], …] for Leaflet polyline."""
    return [
        [G.nodes[n]['y'], G.nodes[n]['x']]
        for n in path_nodes
        if n in G.nodes
    ]
