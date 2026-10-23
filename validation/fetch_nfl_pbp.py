"""Download public nflverse season play-by-play parquet and retain minimal columns."""
import argparse
from pathlib import Path
import pandas as pd
import requests
from io import BytesIO

FIELDS=["game_id","posteam","defteam","epa","success","play_type"]
URL="https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,default=2013)
    p.add_argument("--end",type=int,default=2025)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    if a.start>a.end:raise ValueError("Invalid range")
    parts=[]
    for season in range(a.start,a.end+1):
        url=URL.format(season=season)
        response=requests.get(url,timeout=150);response.raise_for_status()
        rows=pd.read_parquet(BytesIO(response.content),columns=FIELDS)
        rows=rows.dropna(subset=["game_id","posteam","defteam","epa","success"])
        rows=rows[rows.play_type.isin(["pass","run"])]
        parts.append(rows)
        print(season,len(rows),flush=True)
    result=pd.concat(parts,ignore_index=True)
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    result.to_parquet(target,index=False)
    print("stored",len(result),"plays")
if __name__=="__main__":main()
