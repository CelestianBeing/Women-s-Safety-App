"""
Edge safety score computation using OSM attributes + community incident reports.
"""
import os
import logging
from datetime import datetime, timedelta

import osmnx as ox
import networkx as nx
from geopy.distance import geodesic

from config import Config

logger = logging.getLogger(__name__)


# ── Graph loading ────────────────────────────────────────────────────────────

def load_graph() -> nx.MultiDiGraph:
    """Return cached OSM walk graph, downloading if needed."""
    os.makedirs(Config.DATA_DIR, exist_ok=True)
    if os.path.exists(Config.GRAPH_FILE):
        logger.info("Loading cached graph from %s", Config.GRAPH_FILE)
        return ox.load_graphml(Config.GRAPH_FILE)
    logger.info("Downloading street network for '%s'…", Config.PLACE_NAME)
    G = ox.graph_from_place(Config.PLACE_NAME, network_type='walk')
    ox.save_graphml(G, Config.GRAPH_FILE)
    logger.info("Graph saved (%d nodes, %d edges)", G.number_of_nodes(), G.number_of_edges())
    return G


# ── Amenity helpers ───────────────────────────────────────────────────────────

def _fetch_amenity_centroids(place: str, tags: dict) -> list[tuple]:
    """Return list of (lat, lng) for given OSM amenity tags."""
    try:
        features = ox.features_from_place(place, tags=tags)
        pts = []
        for row in features.itertuples():
            geom = getattr(row, 'geometry', None)
            if geom:
                c = geom.centroid
                pts.append((c.y, c.x))
        return pts
    except Exception as exc:
        logger.warning("Could not fetch amenity %s: %s", tags, exc)
        return []


def _min_dist(centroid: tuple, points: list[tuple]) -> float:
    if not points:
        return 99999.0
    return min(geodesic(centroid, p).meters for p in points)


# ── Score computation ─────────────────────────────────────────────────────────

def calculate_edge_safety(G: nx.MultiDiGraph) -> None:
    """
    Compute initial OSM-attribute-based safety scores for all edges and
    persist them to EdgeSafety table (upsert).  Safe to call multiple times.
    """
    # Import here to avoid circular import at module level
    from models import EdgeSafety, db

    police_pts  = _fetch_amenity_centroids(Config.PLACE_NAME, {'amenity': 'police'})
    hosp_pts    = _fetch_amenity_centroids(Config.PLACE_NAME, {'amenity': 'hospital'})
    light_pts   = _fetch_amenity_centroids(Config.PLACE_NAME, {'highway': 'street_lamp'})

    logger.info("Scoring %d edges…", G.number_of_edges())

    # Build lookup for existing rows (avoid N+1 queries)
    existing: dict[str, EdgeSafety] = {
        e.edge_key: e for e in EdgeSafety.query.all()
    }

    new_edges   = []
    batch_size  = 500
    count       = 0

    for u, v, key, data in G.edges(keys=True, data=True):
        edge_key   = f"{u}-{v}-{key}"
        road_type  = data.get('highway', '')
        if isinstance(road_type, list):
            road_type = road_type[0]

        # --- Road width approximation ---
        try:
            road_width = float(str(data.get('width', '')).split()[0])
        except (ValueError, TypeError, IndexError):
            width_map = {'primary': 12, 'secondary': 10, 'tertiary': 8,
                         'residential': 6, 'footway': 3, 'path': 2}
            road_width = width_map.get(road_type, 4)

        # --- Base score ---
        score = 50.0

        # Road type bonuses
        type_bonus = {'primary': 12, 'secondary': 10, 'tertiary': 7,
                      'residential': 5, 'footway': 3, 'path': -5}
        score += type_bonus.get(road_type, 0)

        # Width (capped)
        score += min(road_width, 15) * 0.5

        # Sidewalk / lit tags
        if data.get('sidewalk') in ('both', 'left', 'right', 'yes'):
            score += 8
        if data.get('lit') == 'yes':
            score += 10
        elif data.get('lit') == 'no':
            score -= 8

        # Edge centroid
        cent = (
            (G.nodes[u]['y'] + G.nodes[v]['y']) / 2,
            (G.nodes[u]['x'] + G.nodes[v]['x']) / 2,
        )

        # Proximity bonuses
        pd = _min_dist(cent, police_pts)
        score += 15 if pd < 200 else (10 if pd < 500 else (5 if pd < 1000 else 0))

        hd = _min_dist(cent, hosp_pts)
        score += 10 if hd < 300 else (5 if hd < 800 else 0)

        ld = _min_dist(cent, light_pts)
        score += 8 if ld < 50 else (4 if ld < 150 else 0)

        score = float(max(1, min(99, score)))

        row = existing.get(edge_key)
        if row:
            row.safety_score = score
            row.updated_at   = datetime.utcnow()
        else:
            new_edges.append(EdgeSafety(edge_key=edge_key, safety_score=score, confidence=20.0))

        count += 1
        if count % batch_size == 0:
            if new_edges:
                db.session.bulk_save_objects(new_edges)
                new_edges.clear()
            db.session.commit()
            logger.info("  … %d edges processed", count)

    if new_edges:
        db.session.bulk_save_objects(new_edges)
    db.session.commit()
    logger.info("Edge safety scores stored (%d total).", count)


# ── Real-time score lookup ────────────────────────────────────────────────────

def get_edge_safety(u, v, key, G: nx.MultiDiGraph) -> tuple[float, float]:
    """
    Return (safety_score, confidence) for an edge, adjusted for recent reports.
    Reads from DB; falls back to 50/10 if edge not found.
    """
    from models import EdgeSafety, IncidentReport

    edge_key = f"{u}-{v}-{key}"
    row = EdgeSafety.query.filter_by(edge_key=edge_key).first()
    base_score = row.safety_score if row else 50.0
    confidence = row.confidence   if row else 10.0

    cent = (
        (G.nodes[u]['y'] + G.nodes[v]['y']) / 2,
        (G.nodes[u]['x'] + G.nodes[v]['x']) / 2,
    )

    cutoff = datetime.utcnow() - timedelta(days=7)
    recent = IncidentReport.query.filter(
        IncidentReport.timestamp > cutoff,
        IncidentReport.resolved.is_(False),
    ).all()

    penalty = 0.0
    for rep in recent:
        dist = geodesic(cent, (rep.latitude, rep.longitude)).meters
        if dist < 300:
            # Higher severity + closer proximity = bigger penalty
            weight    = max(0.0, 1 - dist / 300)
            penalty  += rep.severity * 4 * weight

    final = float(max(1.0, min(99.0, base_score - penalty)))
    return final, confidence
