"""Auditably remove known exhibition and NBA Cup final fixtures from regular-season ESPN results.

Exclusion must be explainable from verified competition dates and matchups.
Reject any dataset that is not exactly 30 teams x 82 games after filtering.
"""
from collections import Counter
from datetime import datetime,timezone

# Independently verified NBA Cup final dates (UTC) and opponents.
CUP_FINALS={
    2024:("2023-12-10",frozenset(("LAL","IND"))),
    2025:("2024-12-18",frozenset(("MIL","OKC"))),
    2026:("2025-12-17",frozenset(("NY","SA"))),
}
# Source scoreboard uses NY and SA for some seasons; compare only exact observed codes.
# Exhibit teams are identified by their absence from the 30 established franchises:
# a real franchise must appear in at least 70 season games.
def clean(games):
    byyear={}
    for g in games:
        byyear.setdefault(int(g["season"]),[]).append(g)
    cleaned=[];rejected=[];reports={}
    for season,rows in sorted(byyear.items()):
        counts=Counter(t for g in rows for t in (g["home_team"],g["away_team"]))
        franchises={t for t,n in counts.items() if n>=70}
        if len(franchises)!=30:
            raise ValueError(f"Cannot establish 30 franchises in {season}: {len(franchises)}")
        for g in rows:
            sides=frozenset((g["home_team"],g["away_team"]))
            reason=None
            if not sides.issubset(franchises):
                reason="exhibition_nonfranchise"
            elif season in CUP_FINALS:
                cup_date,cup_sides=CUP_FINALS[season]
                dt=datetime.fromisoformat(g["tipoff_utc"].replace("Z","+00:00"))
                if dt.tzinfo is None:raise ValueError("UTC tipoff required")
                if dt.astimezone(timezone.utc).date().isoformat()==cup_date and sides==cup_sides:
                    reason="nba_cup_championship_not_regular_season"
            if reason:rejected.append({"season":season,"game_id":g["game_id"],"reason":reason,
                                       "home_team":g["home_team"],"away_team":g["away_team"]})
            else:cleaned.append(g)
        current=[g for g in cleaned if int(g["season"])==season]
        after=Counter(t for g in current for t in (g["home_team"],g["away_team"]))
        reports[str(season)]={"before":len(rows),"after":len(current),
            "removed":len(rows)-len(current),
            "30_teams_82_games_verified":len(current)==1230 and len(after)==30 and all(v==82 for v in after.values())}
        if not reports[str(season)]["30_teams_82_games_verified"]:
            raise ValueError(f"Historical regular-season coverage remains unresolved for {season}: {reports[str(season)]}")
    return cleaned,{"coverage_verified":True,"seasons":reports,"excluded_games":rejected}
