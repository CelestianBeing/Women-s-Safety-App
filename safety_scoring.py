import osmnx as ox
import networkx as nx
import pandas as pd
import numpy as np
from geopy.distance import geodesic
from models import IncidentReport, EdgeSafety, db
from config import Config
import json

# Preload graph (cached)
def load_graph():
    if not os.path.exists(Config.GRAPH_FILE):
        print("Downloading street network...")
        G = ox.graph_from_place(Config.PLACE_NAME, network_type='walk')
        ox.save_graphml(G, Config.GRAPH_FILE)
    else:
        G = ox.load_graphml(Config.GRAPH_FILE)
    return G

def calculate_edge_safety(G):
    """Compute initial safety scores for all edges based on OSM attributes."""
    # Get amenities
    police_stations = ox.features_from_place(Config.PLACE_NAME, tags={'amenity': 'police'})
    hospitals = ox.features_from_place(Config.PLACE_NAME, tags={'amenity': 'hospital'})
    # For simplicity, use centroids
    police_points = [(p.geometry.centroid.y, p.geometry.centroid.x) for p in police_stations.itertuples() if hasattr(p, 'geometry')]
    hospital_points = [(h.geometry.centroid.y, h.geometry.centroid.x) for h in hospitals.itertuples() if hasattr(h, 'geometry')]

    # Build safety scores
    edge_safety = {}
    for u, v, key, data in G.edges(keys=True, data=True):
        road_type = data.get('highway', '')
        road_width = data.get('width', None)
        if road_width is None:
            # approximate
            if road_type in ['primary', 'secondary', 'tertiary']:
                road_width = 10
            elif road_type == 'residential':
                road_width = 6
            else:
                road_width = 4

        # Base score
        score = 50
        # Road type
        if road_type in ['primary', 'secondary']:
            score += 10
        elif road_type == 'residential':
            score += 5
        # Wider road safer
        score += min(road_width, 15) * 0.5

        # Proximity to police stations (closer = safer)
        edge_centroid = ((G.nodes[u]['y'] + G.nodes[v]['y'])/2, (G.nodes[u]['x'] + G.nodes[v]['x'])/2)
        min_police_dist = 1000
        if police_points:
            min_police_dist = min(geodesic(edge_centroid, p).meters for p in police_points)
        if min_police_dist < 200:
            score += 15
        elif min_police_dist < 500:
            score += 10
        elif min_police_dist < 1000:
            score += 5

        # Proximity to hospitals (softer)
        min_hosp_dist = 1000
        if hospital_points:
            min_hosp_dist = min(geodesic(edge_centroid, h).meters for h in hospital_points)
        if min_hosp_dist < 300:
            score += 10
        elif min_hosp_dist < 800:
            score += 5

        # Subtract based on nearby incident reports (after initial calculation)
        # We'll apply recent crime data later; start with neutral.
        # Clamp
        score = max(1, min(99, score))
        edge_key = f"{u}-{v}-{key}"
        edge_safety[edge_key] = score

        # Store in DB (initial)
        existing = EdgeSafety.query.filter_by(edge_key=edge_key).first()
        if not existing:
            new_edge = EdgeSafety(edge_key=edge_key, safety_score=score, confidence=20)
            db.session.add(new_edge)
    db.session.commit()
    return edge_safety

def update_safety_from_reports():
    """Recalculate edge safety scores incorporating recent incident reports."""
    # Get all reports from last 30 days
    from datetime import datetime, timedelta
    recent = IncidentReport.query.filter(IncidentReport.timestamp > datetime.utcnow() - timedelta(days=30)).all()
    # For each edge, sum severity*weight for proximity
    edges = EdgeSafety.query.all()
    for edge in edges:
        u, v, key = edge.edge_key.split('-')
        # get centroid from graph
        # This requires loading graph. For brevity, we'll recompute on route planning.
        pass

def get_edge_safety(u, v, key, G):
    """Get current safety score for an edge, with real-time report adjustment."""
    edge_key = f"{u}-{v}-{key}"
    edge_db = EdgeSafety.query.filter_by(edge_key=edge_key).first()
    base_score = edge_db.safety_score if edge_db else 50
    # Reduce score based on nearby recent reports
    cent = ((G.nodes[u]['y'] + G.nodes[v]['y'])/2, (G.nodes[u]['x'] + G.nodes[v]['x'])/2)
    from datetime import datetime, timedelta
    recent_reports = IncidentReport.query.filter(
        IncidentReport.timestamp > datetime.utcnow() - timedelta(days=7)
    ).all()
    penalty = 0
    for rep in recent_reports:
        dist = geodesic(cent, (rep.latitude, rep.longitude)).meters
        if dist < 200:
            penalty += rep.severity * max(0, 10 - dist/20)
    final_score = max(1, min(99, base_score - penalty))
    return final_score, edge_db.confidence if edge_db else 10