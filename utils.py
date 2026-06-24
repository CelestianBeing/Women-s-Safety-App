"""
Helper utilities: confidence scoring, safety-twins detection, rate limiting.
"""
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ── Confidence scoring ────────────────────────────────────────────────────────

def compute_confidence(reports_count: int) -> float:
    """
    Return confidence 0–100 based on number of incident reports near an edge.
    The more data, the higher our confidence in the safety score.
    """
    if reports_count == 0:
        return 10.0
    if reports_count < 3:
        return 20.0 + reports_count * 8
    if reports_count < 10:
        return 40.0 + (reports_count - 3) * 5
    if reports_count < 30:
        return 75.0 + (reports_count - 10) * 0.5
    return min(95.0, 85.0 + reports_count * 0.1)


# ── Safety-twins detection ────────────────────────────────────────────────────

def find_safety_twins(user_id: int, route_nodes: list,
                      current_time: datetime,
                      max_time_diff_min: int = 30) -> int:
    """
    Return the count of other active travelers whose route overlaps ≥50%
    with *route_nodes* and who started travelling within *max_time_diff_min*.
    """
    if not route_nodes:
        return 0

    from models import ActiveTraveler  # local import to avoid circular

    cutoff     = current_time - timedelta(minutes=max_time_diff_min)
    my_set     = set(route_nodes)
    twins      = 0

    try:
        travelers = (
            ActiveTraveler.query
            .filter(
                ActiveTraveler.user_id  != user_id,
                ActiveTraveler.last_update >= cutoff,
            )
            .all()
        )
        for t in travelers:
            their_nodes = t.route_nodes   # uses the @property from model
            if not their_nodes:
                continue
            their_set = set(their_nodes)
            overlap   = len(my_set & their_set)
            threshold = 0.5 * min(len(my_set), len(their_set))
            if overlap >= threshold:
                twins += 1
    except Exception as exc:
        logger.warning("find_safety_twins error: %s", exc)

    return twins


# ── Simple in-memory rate limiter ─────────────────────────────────────────────

_rate_buckets: dict[str, list[datetime]] = {}

def check_rate_limit(key: str, max_calls: int, window_seconds: int) -> bool:
    """
    Return True if *key* has made fewer than *max_calls* in the last
    *window_seconds*.  Side-effect: records the current call.
    """
    now    = datetime.utcnow()
    cutoff = now - timedelta(seconds=window_seconds)
    bucket = _rate_buckets.get(key, [])
    # Evict old entries
    bucket = [t for t in bucket if t > cutoff]
    if len(bucket) >= max_calls:
        return False
    bucket.append(now)
    _rate_buckets[key] = bucket
    return True


# ── Input validation helpers ──────────────────────────────────────────────────

def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def validate_latlng(lat: float, lng: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lng <= 180
