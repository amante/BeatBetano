"""Hourly NHL pregame capture window with tolerance for delayed Actions starts."""
from datetime import timedelta


def active_capture_window(now, starts):
    """Capture from two hours before first puck drop until the last game starts."""
    starts=list(starts)
    if not starts:
        return False
    if now.tzinfo is None or any(start.tzinfo is None for start in starts):
        raise ValueError("Capture window timestamps must be timezone-aware")
    first=min(starts)
    last=max(starts)
    return first-timedelta(hours=2) <= now < last
