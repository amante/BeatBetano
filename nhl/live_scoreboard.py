"""Publish read-only NHL live snapshots without browser CORS dependencies."""
import json
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.request import urlopen

def get(url):
 with urlopen('https://api-web.nhle.com/v1/'+url,timeout=20) as r:return json.load(r)

def main():
 now=datetime.now(timezone.utc);games={};errors=[]
 for delta in (-1,0):
  day=(now.date()+timedelta(days=delta)).isoformat()
  for game in get('score/'+day).get('games',[]):
   try:
    gid=str(game['id']);games[gid]=get('gamecenter/'+gid+'/landing')
   except (OSError,ValueError) as e:errors.append(str(game['id']))
 path=Path('frontend/data/nhl-live-scoreboard.json');path.write_text(json.dumps(dict(as_of_utc=datetime.now(timezone.utc).isoformat(),games=games,errors=errors)))
if __name__=='__main__':main()
