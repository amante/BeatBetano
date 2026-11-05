"""Decide when to capture NHL pregame evidence for a Santiago-local slate."""
import argparse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from nhl.pregame_fixture_goalie_verifier import capture_schedule

CHILE = ZoneInfo("America/Santiago")


def slate_window(now=None, fetch=capture_schedule):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Current time must include a timezone")
    now = now.astimezone(timezone.utc)
    local_day = now.astimezone(CHILE).date()

    # Fixtures around local midnight may be filed under an adjacent NHL
    # schedule date. Fetch three dates, then group fixtures by Chile start day.
    fixtures = {}
    for offset in (-1, 0, 1):
        schedule_day = (local_day + timedelta(days=offset)).isoformat()
        for fixture in fetch(schedule_day)["fixtures"]:
            fixtures[str(fixture["game_id"])] = fixture

    groups = {}
    for fixture in fixtures.values():
        start = datetime.fromisoformat(fixture["scheduled_start"].replace("Z", "+00:00"))
        if start.tzinfo is None:
            raise ValueError("Fixture start must include a timezone")
        groups.setdefault(start.astimezone(CHILE).date(), []).append(start.astimezone(timezone.utc))

    candidates = []
    for day, starts in groups.items():
        first, last = min(starts), max(starts)
        target = first - timedelta(hours=2)
        if target <= now < last:
            candidates.append((target, day, first, last))
    if not candidates:
        return {"should_run": False, "day": local_day.isoformat(), "reason": "outside_slate_window"}

    target, day, first, last = min(candidates)
    # Use the scheduled half-hour tick, not runner start time, so normal
    # GitHub queue delays do not shift the hourly cadence or duplicate a slot.
    tick = datetime.fromtimestamp((int(now.timestamp()) // 1800) * 1800, timezone.utc)
    elapsed = (tick - target).total_seconds()
    # The scheduler polls every 30 minutes. This gate takes the first poll
    # within each hourly slot, starting no earlier than the two-hour target.
    if elapsed < 0 or elapsed % 3600 >= 1800 or now >= last:
        return {"should_run": False, "day": day.isoformat(), "reason": "outside_hourly_capture_slot",
                "first_start_utc": first.isoformat(), "last_start_utc": last.isoformat()}
    return {"should_run": True, "day": day.isoformat(), "reason": "pregame_hourly_capture",
            "first_start_utc": first.isoformat(), "last_start_utc": last.isoformat()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-output", required=True)
    args = parser.parse_args()
    result = slate_window()
    with open(args.github_output, "a", encoding="utf-8") as output:
        for key, value in result.items():
            output.write(f"{key}={str(value).lower() if isinstance(value, bool) else value}\n")
    print(result)


if __name__ == "__main__":
    main()
