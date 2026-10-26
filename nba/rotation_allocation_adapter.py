"""NBA conservative regulation-minute adapter for shared allocator.

Requires complete eligible-player list from separately verified team/availability.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"multisport"))
from opportunity_allocation import allocate

def project_nba_minutes(roster):
 if not isinstance(roster,dict) or roster.get("roster_complete") is not True:
  return {"status":"incomplete_roster","allocations":None}
 if roster.get("availability_source_verified") is not True:
  return {"status":"unverified_availability","allocations":None}
 return allocate("nba","minutes",roster["players"])
