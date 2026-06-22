import numpy as np
from datetime import datetime, timedelta
from models import ActiveTraveler, IncidentReport, EdgeSafety

def compute_confidence(edge_key, reports_count):
    """Return confidence (0-100) based on number of incident reports near edge."""
    if reports_count == 0:
        return 10.0
    elif reports_count < 5:
        return 30.0 + reports_count * 10
    elif reports_count < 20:
        return 70.0
    else:
        return min(95.0, 80 + reports_count)

def find_safety_twins(user_id, route_nodes, current_time, max_time_diff_min=30):
    """Find other active travelers with similar route."""
    if not route_nodes:
        return 0
    set_route = set(route_nodes)
    twins = 0
    active_travelers = ActiveTraveler.query.filter(
        ActiveTraveler.user_id != user_id,
        ActiveTraveler.start_time >= current_time - timedelta(minutes=max_time_diff_min)
    ).all()
    for trav in active_travelers:
        import json
        try:
            their_nodes = json.loads(trav.route_nodes_json)
        except:
            continue
        their_set = set(their_nodes)
        overlap = len(set_route & their_set)
        if overlap > 0.5 * min(len(set_route), len(their_set)):
            twins += 1
    return twins