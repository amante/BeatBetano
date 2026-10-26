"""Merge verified, time-stamped NFL availability/weather observations.

Never infer an inactive, starter or numerical win/prop adjustment from an
ESPN injury listing. Verified facts must have explicit provenance.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path

POSITIONS={"QB","RB","WR","TE","LT","LG","C","RG","RT","OL","EDGE","DE","DT","LB","CB","NB","S","K","P"}
STATES={"active","inactive","questionable","doubtful","out","unknown"}

def instant(value):
    dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if dt.tzinfo is None:raise ValueError("Timestamp missing timezone")
    return dt.astimezone(timezone.utc)

def reconcile(slate,evidence,verified=None):
    if slate.get("sport")!="nfl":raise ValueError("NFL slate required")
    verified=verified or {"games":[]}
    byid={}
    for r in verified.get("games",[]):
        gid=str(r["event_id"])
        if gid in byid:raise ValueError("Duplicate verified event")
        byid[gid]=r
    supplements={str(r["event_id"]):r for r in evidence.get("games",[])}
    result=[]
    for game in slate["events"]:
        gid=str(game["event_id"]);tip=instant(game["start_utc"])
        teams={game["home_team"],game["away_team"]}
        v=byid.get(gid,{})
        participants=[];failures=[]
        for player in v.get("players",[]):
            team=player.get("team");position=player.get("position")
            state=player.get("status")
            observed=player.get("observed_at_utc")
            source=player.get("source_url")
            try:timely=instant(observed)<tip and instant(observed)<=instant(slate["as_of_utc"])
            except (ValueError,TypeError):timely=False
            if not (team in teams and position in POSITIONS and state in STATES and timely and
                    isinstance(source,str) and source.startswith("https://") and player.get("player_id")):
                failures.append("unverified_player_evidence")
                continue
            participants.append({"player_id":str(player["player_id"]),"team":team,
               "position":position,"status":state,"source_url":source,
               "observed_at_utc":observed,"official_inactive_confirmed":
               state=="inactive" and player.get("source_is_official") is True,
               "starter_confirmed":player.get("starter_confirmed") is True and
               player.get("source_is_official") is True})
        w=v.get("weather",{})
        weather=None
        if isinstance(w,dict) and w:
            try:good=instant(w["observed_at_utc"])<=instant(slate["as_of_utc"]) and instant(w["observed_at_utc"])<tip
            except (KeyError,TypeError,ValueError):good=False
            if (good and isinstance(w.get("source_url"),str) and w["source_url"].startswith("https://") and
                w.get("venue_id") and isinstance(w.get("wind_mph"),(int,float)) and
                0<=w["wind_mph"]<=150):
                weather={"wind_mph":w["wind_mph"],"source_url":w["source_url"],
                         "observed_at_utc":w["observed_at_utc"],"venue_id":w["venue_id"],
                         "forecast_not_measured":True}
            else:failures.append("weather_unverified")
        secondary=[p for p in participants if p["position"] in {"CB","NB","S"} and p["official_inactive_confirmed"]]
        result.append({"event_id":gid,"teams":sorted(teams),"verified_players":participants,
          "confirmed_secondary_inactives":secondary,"weather_forecast":weather,
          "espn_supplement_available":gid in supplements,
          "missing_evidence":sorted(set(failures+["coverage_scheme","usage_projection",
            "player_prop_calibration","starter_return_impact_validation"])),
          "winner_log_odds_adjustment":None,"prop_predictions":None,
          "validation_approved":False})
    return {"schema_version":1,"sport":"nfl","games":result,
      "verified_source_required":True,"odds_used":False,
      "note":"No unsupported impact or prop probabilities. Only explicitly sourced as-of facts."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--slate",required=True);p.add_argument("--supplement",required=True)
    p.add_argument("--verified");p.add_argument("--output",required=True)
    a=p.parse_args()
    load=lambda f:json.loads(Path(f).read_text()) if f and Path(f).exists() else {}
    out=reconcile(load(a.slate),load(a.supplement),load(a.verified))
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,indent=2))
    print(json.dumps({"events":len(out["games"]),"confirmed_secondary_inactives":
       sum(len(g["confirmed_secondary_inactives"]) for g in out["games"])}))
if __name__=="__main__":main()
