"""NHL goalie daily evidence: raw measured form, workload and confirmation provenance.

This is not a fitted Goalie Daily Rating or a probability adjustment.
"""
from datetime import datetime, timezone
import math

def utc(s):
    d=datetime.fromisoformat(str(s).replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("Timezone required")
    return d.astimezone(timezone.utc)

def assess(record,team,freeze,tipoff):
    if not isinstance(record,dict) or record.get("team")!=team:
        return {"status":"missing_or_wrong_team","confirmed":False,"rating":None}
    try:
        timely=utc(record["observed_at_utc"])<=utc(freeze)<utc(tipoff)
        src=record["source_url"]
    except (KeyError,ValueError,TypeError):
        timely=False;src=None
    if not timely or not isinstance(src,str) or not src.startswith("https://"):
        return {"status":"unverified_or_late","confirmed":False,"rating":None}
    # A probable goalie may be shown as an observation, never as confirmed.
    confirmed=record.get("starter_status")=="confirmed" and record.get("official_confirmation") is True
    if record.get("starter_status") not in ("confirmed","probable","unknown"):
        return {"status":"invalid_starter_status","confirmed":False,"rating":None}
    shots=record.get("shots_against");saves=record.get("saves")
    games=record.get("sample_games")
    if not (type(shots) is int and type(saves) is int and type(games) is int
            and shots>=saves>=0 and games>0):
        return {"status":"insufficient_verified_save_sample","confirmed":confirmed,"rating":None}
    gsa=record.get("gsax")
    if gsa is not None and (type(gsa) not in (int,float) or not math.isfinite(gsa)):
        raise ValueError("Invalid GSAx")
    starts7=record.get("starts_last_7_days")
    if starts7 is not None and (type(starts7) is not int or not 0<=starts7<=7):
        raise ValueError("Invalid workload")
    return {"status":"measured_unfitted","goalie_id":record.get("goalie_id"),
        "team":team,"starter_status":record["starter_status"],"confirmed":confirmed,
        "save_percentage":round(saves/shots,6) if shots else None,
        "shots_against":shots,"saves":saves,"sample_games":games,
        "gsax":gsa,"gsax_per_game":round(gsa/games,6) if gsa is not None else None,
        "starts_last_7_days":starts7,"source_url":src,
        "observed_at_utc":record["observed_at_utc"],"rating":None,
        "win_probability_delta":None,"validated":False}

def matchup(evidence,home,away,freeze,tipoff):
    x=evidence if isinstance(evidence,dict) else {}
    return {"home":assess(x.get("home"),home,freeze,tipoff),
      "away":assess(x.get("away"),away,freeze,tipoff),
      "both_starters_confirmed":False if not x else all(
          assess(x.get(k),team,freeze,tipoff)["confirmed"] for k,team in
          (("home",home),("away",away))),
      "calibrated_goalie_impact":None}
