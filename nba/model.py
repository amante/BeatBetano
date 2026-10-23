"""NBA official candidate v0.1: transparent odds-free chronological Elo baseline.

This is NOT the calibrated full 2026-27 official model yet. Input games must
contain verified point-in-time results. No bookmaker odds or postgame data are
ever features of a pregame prediction.
"""
from dataclasses import dataclass
import math

HOME_ADVANTAGE=65.0
K_FACTOR=20.0
SEASON_RETENTION=0.75

@dataclass(frozen=True)
class Prediction:
    season: int
    date: str
    game_id: str
    away: str
    home: str
    p_away: float
    p_home: float
    prior_games_away: int
    prior_games_home: int
    dual_eligible: bool

def probability(home_rating,away_rating):
    diff=home_rating+HOME_ADVANTAGE-away_rating
    return 1.0/(1.0+10.0**(-diff/400))

def dual_eligible(p_home):
    return abs(2*p_home-1)<=0.06+1e-12

def evaluate(games,season_min=2023,season_max=2025):
    """Yield pregame predictions, update ratings only after each completed game.

    Rows MUST be ordered by actual tipoff timestamp, with unique game IDs.
    A matchup on a date without a timestamp is insufficient for safe walk-forward.
    No external market columns are consumed.
    """
    records=list(games)
    seen=set();ratings={};counts={};last_season=None;prev_tipoff=None
    for row in records:
        required={"game_id","season","tipoff_utc","home_team","away_team",
                  "home_points","away_points"}
        missing=required-set(row)
        if missing:raise ValueError(f"Missing columns: {sorted(missing)}")
        season=int(row["season"])
        if not season_min<=season<=season_max:raise ValueError("Out-of-scope season")
        tipoff=str(row["tipoff_utc"])
        from datetime import datetime, timezone
        parsed=datetime.fromisoformat(tipoff.replace("Z","+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            raise ValueError("tipoff_utc must include explicit UTC timezone")
        if prev_tipoff is not None and parsed<prev_tipoff:
            raise ValueError("Games are not sorted chronologically")
        if season<last_season if last_season is not None else False:
            raise ValueError("Season decreases")
        prev_tipoff=parsed
        gid=str(row["game_id"])
        if gid in seen:raise ValueError("Duplicate game_id")
        seen.add(gid)
        home=str(row["home_team"]);away=str(row["away_team"])
        if not home or not away or home==away:raise ValueError("Invalid teams")
        if last_season is not None and season!=last_season:
            ratings={t:1500+SEASON_RETENTION*(r-1500) for t,r in ratings.items()}
            counts={}
        last_season=season
        rh=ratings.get(home,1500.0);ra=ratings.get(away,1500.0)
        p=probability(rh,ra)
        result=Prediction(season,tipoff,gid,away,home,1-p,p,counts.get(away,0),counts.get(home,0),dual_eligible(p))
        yield result
        hp=row["home_points"];ap=row["away_points"]
        if hp is None or ap is None:
            # Future games cannot train the predictor or fabricate a result.
            continue
        hp=float(hp);ap=float(ap)
        if not math.isfinite(hp) or not math.isfinite(ap) or hp==ap:
            raise ValueError("Completed NBA games require finite non-tied scores")
        d=K_FACTOR*((1.0 if hp>ap else 0.0)-p)
        ratings[home]=rh+d;ratings[away]=ra-d
        counts[home]=counts.get(home,0)+1;counts[away]=counts.get(away,0)+1

def score(predictions,games):
    """Paired calibration metrics only for games with final scores."""
    p=list(predictions);g=list(games)
    if len(p)!=len(g):raise ValueError("Length mismatch")
    vals=[]
    for pred,row in zip(p,g):
        if pred.game_id!=str(row["game_id"]):raise ValueError("Misaligned game_id")
        if row["home_points"] is None or row["away_points"] is None:continue
        y=float(row["home_points"])>float(row["away_points"])
        prob=max(1e-12,min(1-1e-12,pred.p_home))
        vals.append((float(y),prob))
    if not vals:raise ValueError("No completed games")
    n=len(vals)
    return {"n":n,
            "brier":sum((y-v)**2 for y,v in vals)/n,
            "log_loss":-sum(y*math.log(v)+(1-y)*math.log1p(-v) for y,v in vals)/n}
