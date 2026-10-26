"""Fetch historical ESPN team box scores for possession model."""
import argparse,json
from pathlib import Path
from possession_intelligence import capture
def main():
 p=argparse.ArgumentParser()
 for a in ("history","output"):p.add_argument("--"+a,required=True)
 p.add_argument("--limit",type=int,default=80)
 a=p.parse_args()
 if not 1<=a.limit<=200:raise ValueError("Limit out of range")
 report=capture(json.loads(Path(a.history).read_text()),limit=a.limit)
 target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,indent=2))
 print(json.dumps({"team_games":len(report["games"]),"errors":len(report["errors"])}))
if __name__=="__main__":main()
