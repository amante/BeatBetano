"""Sport-independent allocation of scarce participation/opportunities.

Allocations are joint and conditional on availability, never independent raw
player averages. No betting inputs and no production probability adjustment.
"""
from math import isfinite

SPORTS={
 "nba":{"minutes":240.0},
 "soccer":{"minutes":990.0},
 "nhl":{"skater_minutes":300.0,"goalie_minutes":60.0},
 "nfl":{}
}
def allocate(sport,unit,players,total=None):
 if sport not in SPORTS:raise ValueError("Unsupported sport (tennis excluded)")
 if unit not in ("minutes","skater_minutes","goalie_minutes","targets","carries","snaps","shots","powerplay_minutes"):
  raise ValueError("Unknown unit")
 fixed=SPORTS[sport].get(unit)
 if total is None:total=fixed
 if total is None or type(total) not in (int,float) or not isfinite(total) or total<0:
  raise ValueError("Explicit finite opportunity budget required")
 if fixed is not None and abs(total-fixed)>1e-7:
  raise ValueError("Regulation budget mismatch")
 if not isinstance(players,list) or len({p.get("player_id") for p in players})!=len(players):
  raise ValueError("Duplicate player ids")
 eligible=[];out=[];uncertain=[]
 for p in players:
  pid=p.get("player_id");status=p.get("status")
  if not isinstance(pid,str) or not pid:raise ValueError("Invalid player id")
  if status not in ("available","out","questionable","unknown"):raise ValueError("Invalid availability")
  weight=p.get("expected_weight");cap=p.get("max_units",total)
  if type(weight) not in (int,float) or not isfinite(weight) or weight<0:raise ValueError("Invalid weight")
  if type(cap) not in (int,float) or not isfinite(cap) or cap<0:raise ValueError("Invalid cap")
  if status=="out":out.append(pid);continue
  if status in ("questionable","unknown"):uncertain.append(pid);continue
  eligible.append((pid,float(weight),min(float(cap),float(total))))
 if uncertain:
  return {"status":"requires_availability_scenarios","sport":sport,"unit":unit,
   "unresolved":uncertain,"out":out,"allocations":None,
   "note":"Resolve or explicitly branch questionable/unknown players; never assume active."}
 if sum(x[2] for x in eligible)+1e-7<total:return {"status":"infeasible","reason":"not_enough_eligible_capacity","allocations":None}
 remaining=float(total);alloc={pid:0.0 for pid,_,_ in eligible};active=list(eligible)
 # Iterative capped weighted allocation: redistribute all released volume.
 while remaining>1e-8 and active:
  weights=sum(w for _,w,_ in active)
  if weights<=0:return {"status":"infeasible","reason":"no_supported_allocation_weights","allocations":None}
  consumed=0.0;next_active=[]
  for pid,w,cap in active:
   amount=min(cap-alloc[pid],remaining*w/weights)
   alloc[pid]+=amount;consumed+=amount
   if cap-alloc[pid]>1e-8:next_active.append((pid,w,cap))
  if consumed<1e-9:break
  remaining-=consumed;active=next_active
 if remaining>1e-5:return {"status":"infeasible","reason":"unallocated_budget","allocations":None}
 return {"status":"provisional_joint_allocation","sport":sport,"unit":unit,"budget":total,
  "allocations":{pid:round(v,5) for pid,v in alloc.items()}|{pid:0.0 for pid in out},
  "residual":round(total-sum(alloc.values()),8),
  "lineups_optimized":False,"calibrated":False,
  "note":"Shares respect caps and availability; role/lineup feasibility and measured absent-player substitutions require sport adapter."}
