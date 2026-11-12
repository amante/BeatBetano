"""#275: user-facing complete NHL experimental research slate.

Retains every official game, all five historical outcome-only markets,
and explicit availability/goalie provenance. Never fake goalie deltas.
"""
import argparse,json,math
from pathlib import Path
from nhl.historical_target_walkforward import CATEGORIES
from nhl.pulso_pregame_v7 import parse_utc

def present(slate,run_id=None):
 if slate.get("kind")!="nhl_daily_complete_slate_274" or slate.get("official") is not False or slate.get("odds_used") is not False:
  raise ValueError("Untrusted daily slate")
 raw=slate["games"]
 if len(raw)!=slate["official_schedule_games"] or len({str(g["game_id"]) for g in raw})!=len(raw):
  raise ValueError("Incomplete or duplicated schedule")
 if run_id is not None and not str(run_id).isdigit():raise ValueError("Numeric run ID required")
 output=[]
 for g in raw:
  state=g["forecast_status"];markets=g.get("markets")
  if state=="experimental_forecast":
   if not isinstance(markets,dict) or set(markets)!=set(CATEGORIES):raise ValueError("Missing market")
   for k,cats in CATEGORIES.items():
    probs=markets[k]
    if not isinstance(probs,dict) or set(probs)!=set(cats):raise ValueError("Wrong market shape")
    if any(type(x) not in (int,float) or not math.isfinite(x) or x<0 or x>1 for x in probs.values()) or abs(sum(probs.values())-1)>1e-6:
     raise ValueError("Non-normalized probabilities")
   if g.get("goalie_conditioned") is not False or g.get("official") is not False:raise ValueError("Misleading probability authority")
  elif state in ("pregame_forecast_unavailable","not_pregame_at_capture"):
   if markets is not None:raise ValueError("Unavailable game has model probabilities")
  else:raise ValueError("Unknown game status")
  ml=markets["ml"] if markets else None
  output.append({"game_id":str(g["game_id"]),"home":g["home"],"away":g["away"],
    "start_utc":g["start_utc"],"status":state,
    "ml":ml,"rt":markets["rt"] if markets else None,
    "home_plus3":markets["home3"]["yes"] if markets else None,
    "away_plus3":markets["away3"]["yes"] if markets else None,
    "first_to_plus3":markets["first3"] if markets else None,
    "home_win_ml":ml["home"] if ml else None,"away_win_ml":ml["away"] if ml else None,
    "goalie_A_vs_B_probabilities":None,"goalies_confirmed":False,
    "module_effects":g.get("module_effects",{}),
    "model":g.get("model_version") if markets else None,
    "probability_status":"research_experimental_not_official" if markets else "not_available"})
 if sum(g["status"]=="experimental_forecast" for g in output)!=slate["experimental_predicted_games"]:
  raise ValueError("Count mismatch")
 return {"kind":"nhl_research_daily_presentation_275","date":slate["date"],
   "source_schedule":slate["schedule_source_url"],"run_id":str(run_id) if run_id is not None else None,
   "official_schedule_games":len(output),"experimental_predicted_games":slate["experimental_predicted_games"],
   "games":output,"official":False,"odds_used":False,
   "limitations":["Outcome-only research baseline, not validated full NHL model",
      "No goalie-conditioned A/B probabilities","RT includes regulation draw",
      "home_plus3 and away_plus3 are not complementary events",
      "First-to-+3 includes neither team",
      "Rest adjusts the ML market only when both prior fixtures are confirmed completed; missing rest leaves that probability unchanged",
      "Travel, officials, goalie, lineup and special-teams adjustments are not part of this rest candidate"]}
def main():
 p=argparse.ArgumentParser();p.add_argument("--slate",required=True);p.add_argument("--out",required=True)
 p.add_argument("--run-id")
 a=p.parse_args();result=present(json.loads(Path(a.slate).read_text()),a.run_id)
 dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(result,indent=2))
 print(json.dumps({"official_schedule_games":result["official_schedule_games"],"experimental_predicted_games":result["experimental_predicted_games"],"markets":["ml","rt","home3","away3","first3"]}))
if __name__=="__main__":main()
