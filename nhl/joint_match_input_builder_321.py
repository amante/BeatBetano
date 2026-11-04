"""Assemble strictly pregame, source-linked input bundles for NHL joint engine #320."""
import argparse, hashlib, json, math
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from nhl.pulso_goalie_multisource_257 import TEAM_NAMES, norm

API = "https://api.nhle.com/stats/rest/en"

def utc(value):
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None: raise ValueError("Source timestamps must include timezone")
    return d.astimezone(timezone.utc)

def season_for(day):
    y, m = int(day[:4]), int(day[5:7]); start = y if m >= 7 else y - 1
    return f"{start}{start+1}"

def get_json(url):
    with urlopen(Request(url, headers={"Accept":"application/json", "User-Agent":"PULSO-NHL-joint/1.0"}), timeout=25) as r:
        raw = r.read(8_000_001)
        if len(raw) > 8_000_000: raise ValueError("Oversized official source")
    return json.loads(raw), {"url":url,"sha256":hashlib.sha256(raw).hexdigest(),"retrieved_at_utc":datetime.now(timezone.utc).isoformat()}

def stat_rows(resource, season, cutoff, sort="playerId:ASC"):
    rows=[];start=0;total=None; sources=[]
    while total is None or start < total:
        q=urlencode({"isAggregate":"false","isGame":"false","start":start,"limit":100,"sort":sort,"cayenneExp":f'seasonId={season} and gameTypeId=2 and gameDate<"{cutoff}"'})
        url=f"{API}/{resource}?{q}"; payload,meta=get_json(url); data=payload.get("data")
        if not isinstance(data,list) or type(payload.get("total")) is not int: raise ValueError("Invalid NHL Stats response: "+resource)
        if total is None: total=payload["total"]
        if payload["total"]!=total or len(data)>100 or (total and not data): raise ValueError("Incomplete NHL Stats pagination: "+resource)
        rows.extend(data);sources.append(meta);start+=len(data)
    if len(rows)!=total: raise ValueError("NHL Stats row count mismatch: "+resource)
    return rows,sources

def number(row,key,positive=False):
    x=row.get(key)
    if type(x) not in (int,float) or not math.isfinite(x) or x < 0 or (positive and x<=0): raise ValueError("Missing/invalid NHL stat "+key)
    return x

def toi(value):
    if type(value) in (float,int) and math.isfinite(value) and value>=0: return value/60 if value>100 else value
    if isinstance(value,str) and ":" in value:
        mm,ss=value.split(":",1)
        if mm.isdigit() and ss.isdigit() and int(ss)<60:return int(mm)+int(ss)/60
    raise ValueError("Invalid NHL time-on-ice value")

def build(report, context, changes, goalies, special, cutoff):
    fixtures={str(g["game_id"]):g for g in report.get("games",[])}
    if len(fixtures)!=len(report.get("games",[])): raise ValueError("Duplicate schedule fixture")
    if context.get("kind")!="nhl_pregame_player_evidence_v1" or changes.get("kind")!="nhl_projected_lineup_changes_v1": raise ValueError("Wrong lineup evidence contract")
    if goalies.get("kind")!="nhl_all_goalie_candidates_history_260": raise ValueError("Wrong goalie history contract")
    day=date.fromisoformat(cutoff); season=season_for(cutoff)
    skaters,s1=stat_rows("skater/summary",season,cutoff)
    toi_rows,s2=stat_rows("skater/timeonice",season,cutoff)
    teams,s3=stat_rows("team/summary",season,cutoff,"teamFullName:ASC")
    pp_rows,s4=stat_rows("team/powerplay",season,cutoff,"teamFullName:ASC")
    pk_rows,s5=stat_rows("team/penaltykill",season,cutoff,"teamFullName:ASC")
    goalie_stats,s6=stat_rows("goalie/summary",season,cutoff)
    # Stats API source observations must precede the earliest included fixture.
    observed=max(utc(x["retrieved_at_utc"]) for x in s1+s2+s3+s4+s5+s6)
    name_to_code={norm(v):k for k,v in TEAM_NAMES.items()}
    def index_teams(rows):
        result={}
        for row in rows:
            code=name_to_code.get(norm(row.get("teamFullName","")))
            if not code or code in result: raise ValueError("Unmapped/duplicate NHL team summary identity")
            result[code]=row
        return result
    pp_index=index_teams(pp_rows);pk_index=index_teams(pk_rows)
    league_opps=sum(number(x,"timesShorthanded") for x in pk_rows)
    league_pp_goals=sum(number(x,"ppGoalsAgainst") for x in pk_rows)
    if not league_opps: raise ValueError("League PK opportunity sample is empty")
    league_pk_rate=league_pp_goals/league_opps
    player={}
    for row in skaters:
        pid=str(row.get("playerId"))
        if not pid.isdigit() or pid in player: raise ValueError("Invalid/duplicate NHL player stats identity")
        player[pid]=row
    toi_by_id={str(x.get("playerId")):x for x in toi_rows}
    if len(toi_by_id)!=len(toi_rows): raise ValueError("Duplicate NHL TOI identity")
    team_by_code=index_teams(teams)
    goalie_rows_by_identity={}
    for row in goalie_stats:
        pid=row.get("playerId"); code=row.get("teamAbbrevs")
        if type(pid) is not int or not isinstance(code,str) or not code:
            raise ValueError("Invalid NHL goalie summary identity")
        goalie_rows_by_identity.setdefault((str(pid),code),[]).append(row)
    goalie_games={str(g["game_id"]):g for g in goalies.get("games",[])}
    change_games={str(g["game_id"]):g for g in changes.get("games",[])}
    context_games={str(g["game_id"]):g for g in context.get("games",[])}
    output=[]; blocked=[]
    def player_record(person,code):
        pid=str(person.get("player_id"));s=player.get(pid);t=toi_by_id.get(pid)
        if not s or not t: raise ValueError(code+" missing official prior player/TOI stats for "+str(person.get("name")))
        abbrevs=str(s.get("teamAbbrevs",""))
        if abbrevs != code: raise ValueError(code+" player season stats are multi-team or wrong-team: "+str(person.get("name")))
        gp=number(s,"gamesPlayed",True)
        minutes={"EV":toi(t.get("evenStrengthTimeOnIcePerGame")),"PP":toi(t.get("powerPlayTimeOnIcePerGame")),"PK":toi(t.get("shorthandedTimeOnIcePerGame"))}
        total=toi(t.get("timeOnIcePerGame"))
        prod={k:number(s,k) for k in ("goals","assists","shots","penaltyMinutes","evGoals","ppGoals","shGoals","evPoints","ppPoints","shPoints")}
        return {"player_id":int(pid),"name":person.get("name") or s.get("skaterFullName"),"team_abbrevs":code,"position":s.get("positionCode"),"availability":"active","games_played":gp,"minutes_per_game":minutes,"total_minutes_per_game":total,"production":prod}
    for gid,f in fixtures.items():
        start=utc(f["start_utc"])
        if start <= observed or start <= utc(report["generated_at_utc"]): continue
        for captured_at in (context.get("as_of_utc"), changes.get("as_of_utc", report["generated_at_utc"]), goalies.get("as_of_utc"), special.get("as_of_utc")):
            if captured_at and utc(captured_at) >= start: raise ValueError("Pregame evidence captured after puck drop")
        try:
            cg=context_games.get(gid); lg=change_games.get(gid); gg=goalie_games.get(gid)
            if not cg or (cg["home"],cg["away"])!=(f["home"],f["away"]): raise ValueError("missing/mismatched projected fixture")
            if not lg or not gg: raise ValueError("missing lineup-change/goalie history fixture")
            sides={};unknown=[]
            for code in (f["home"],f["away"]):
                side=cg["teams"].get(code); diff=lg["teams"].get(code); teamrow=team_by_code.get(code); sp=special.get("teams",{}).get(code)
                if not side or not side.get("projected_skaters_identity_complete") or not diff or diff.get("status")!="projected_changes_observed_not_calibrated": raise ValueError(code+" lineup evidence incomplete")
                if not teamrow or not sp: raise ValueError(code+" team/special-team stats unavailable")
                groups=side["projected"]; lines=[]
                for unit,field in (("forwards","forwards"),("defense","defense")):
                    raw=groups.get(field)
                    expected=4 if unit=="forwards" else 3
                    if not isinstance(raw,list) or len(raw)!=expected: raise ValueError(code+" "+field+" projections incomplete")
                    for i,line in enumerate(raw,1): lines.append({"unit":unit,"line":i,"players":[player_record(p,code) for p in line]})
                incoming=[player_record({"player_id":x["player_id"],"name":x["name"]},code) for x in diff["new_in_projection"]]
                outgoing=[]
                for x in diff["out_of_projection"]:
                    p=player_record({"player_id":x["player_id"],"name":x["name"]},code);p["position"]="D" if x.get("position_group")=="defense" else "F";outgoing.append(p)
                absent=[]
                for field in ("injuries","scratches"):
                    names=groups.get(field)
                    if names is None: unknown.append(code+" "+field+" source missing"); continue
                    for person in names:
                        if not person.get("identity_resolved"): unknown.append(code+" unresolved "+field+": "+str(person.get("name"))); continue
                        p=player_record(person,code);p["availability"]="injury" if field=="injuries" else "scratch";absent.append(p)
                candidates=gg["teams"].get(code,[]);glist=[]
                team_games=number(teamrow,"gamesPlayed",True)
                for g in candidates:
                    if g.get("status")!="observed": raise ValueError(code+" goalie history unavailable")
                    stat_rows_for_goalie=goalie_rows_by_identity.get((str(g["player_id"]),code),[])
                    if len(stat_rows_for_goalie)>1: raise ValueError(code+" duplicate goalie start history")
                    games_started=number(stat_rows_for_goalie[0],"gamesStarted") if stat_rows_for_goalie else 0
                    if games_started>team_games: raise ValueError(code+" goalie starts exceed team games")
                    glist.append({"player_id":g["player_id"],"name":g["name"],"status":"observed","candidate_status":g.get("candidate_status"),"independently_confirmed_starter":False,"games_started_before_cutoff":games_started,"team_games_played_before_cutoff":team_games,"metrics":{"season_to_date":{"shots_against":g["metrics"]["season_to_date"]["shots_against"],"saves":g["metrics"]["season_to_date"]["saves"]}}})
                if not glist: raise ValueError(code+" no goalie candidates")
                candidate_starts=sum(g["games_started_before_cutoff"] for g in glist)
                complete_start_coverage=(candidate_starts==team_games)
                for g in glist:
                    g["starter_probability"]=g["games_started_before_cutoff"]/team_games if complete_start_coverage else None
                goalie_start_distribution={"status":"complete_empirical_share" if complete_start_coverage else "incomplete_candidate_coverage","method":"candidate_games_started_divided_by_team_games_played","team_games_played":team_games,"candidate_starts":candidate_starts,"probabilities_sum_to_one":complete_start_coverage}
                if groups.get("injuries") is None or groups.get("scratches") is None: unknown.append(code+" incomplete availability report")
                exact=[r for r in skaters if r.get("teamAbbrevs")==code]
                multi=[r for r in skaters if code in str(r.get("teamAbbrevs","")).split(",") and r.get("teamAbbrevs")!=code]
                if multi: raise ValueError(code+" traded-player season attribution unresolved")
                totals={k:sum(number(r,k) for r in exact) for k in ("goals","assists","shots","penaltyMinutes","evGoals","evPoints","ppGoals","ppPoints","shGoals","shPoints")}
                gp=number(teamrow,"gamesPlayed",True)
                sides[code]={"projected_lines":lines,"lineup_changes":{"new_in_projection":incoming,"out_of_projection":outgoing},"unavailable_players":absent,"goalie_candidates":glist,"goalie_start_distribution":goalie_start_distribution,"team_summary":teamrow,"special_teams":{"games_played":sp["games_played"],"powerplay_goals":sp["powerplay_goals"],"powerplay_opportunities":sp["powerplay_opportunities"],"opponent_powerplay_goals":sp["opponent_powerplay_goals"],"times_shorthanded":sp["times_shorthanded"]},"team_roster_penalty_minutes":{"total":totals["penaltyMinutes"],"games_played":gp,"unattributed_multi_team_players":0},"team_roster_production":{"player_rows":len(exact),"games_played":gp,"totals":totals,"unattributed_multi_team_players":0},"schedule":{},"_unknown":unknown}
            if unknown: raise ValueError("unresolved real-game inputs: "+"; ".join(unknown))
            cutoff_for_engine=cutoff
            if date.fromisoformat(cutoff_for_engine)>=start.date(): raise ValueError("source cutoff is not strictly before fixture UTC date")
            captured=datetime.now(timezone.utc)
            if captured>=start: raise ValueError("Assembly completed after puck drop")
            manifest=s1+s2+s3+s4+s5+s6
            editor=cg.get("editorial_source")
            if not editor or not editor.get("sha256") or not editor.get("url"): raise ValueError("missing dated editorial lineup provenance")
            editorial_at=utc(cg["feature_as_of_utc"])
            if editorial_at>=start: raise ValueError("late editorial lineup capture")
            manifest.append({"url":editor["url"],"sha256":editor["sha256"],"retrieved_at_utc":editorial_at.isoformat()})
            for source in special.get("sources",[]):
                stamp=source.get("retrieved_at_utc") or source.get("retrieved_at")
                if stamp:
                    if utc(stamp)>=start: raise ValueError("late special-team source")
                    manifest.append({"url":source.get("url"),"sha256":source.get("sha256"),"retrieved_at_utc":utc(stamp).isoformat()})
            for code in (f["home"],f["away"]):
                ref=change_games[gid]["teams"][code].get("reference_source")
                if ref and ref.get("retrieved_at"):
                    if utc(ref["retrieved_at"])>=start: raise ValueError("late prior-lineup reference")
                    manifest.append({"url":ref.get("url"),"sha256":ref.get("sha256"),"retrieved_at_utc":utc(ref["retrieved_at"]).isoformat()})
            for code in (f["home"],f["away"]):
                if code not in pp_index or code not in pk_index: raise ValueError(code+" missing PP/PK source counts")
                stat= special.get("teams",{}).get(code,{})
                if stat.get("powerplay_opportunities",0)<=0 or stat.get("times_shorthanded",0)<=0: raise ValueError(code+" PP/PK sample empty")
            goalie_sources=[]
            for code in (f["home"],f["away"]):
                for g in goalie_games[gid]["teams"].get(code,[]):
                    if g.get("status")=="observed":
                        meta=g.get("source",{}); stamp=utc(meta.get("retrieved_at", ""))
                        if stamp>=start: raise ValueError("post-start goalie statistics")
                        goalie_sources.append({"url":meta.get("url"),"sha256":meta.get("sha256"),"retrieved_at_utc":stamp.isoformat()})
            manifest+=goalie_sources
            if any(utc(x["retrieved_at_utc"])>=start for x in manifest): raise ValueError("Post-start source")
            output.append({"kind":"nhl_joint_match_inputs_v1","game_id":gid,"home":f["home"],"away":f["away"],"start_utc":f["start_utc"],"cutoff_exclusive":cutoff_for_engine,"captured_at_utc":captured.isoformat(),"poststart_reconstruction":False,"league_context":{"powerplay_goals_allowed_per_opportunity":league_pk_rate},"teams":sides,"unknowns":unknown,"source_manifest":manifest})
        except (KeyError,TypeError,ValueError) as e: blocked.append({"game_id":gid,"home":f["home"],"away":f["away"],"reason":str(e)[:240]})
    return {"kind":"nhl_joint_match_input_batch_v321","date":cutoff,"season":season,"generated_at_utc":datetime.now(timezone.utc).isoformat(),"games":output,"blocked_games":blocked,"official":False,"calibrated":False,"odds_used":False}

def main():
    p=argparse.ArgumentParser()
    for key in ("report","context","changes","goalies","special-teams","output"):p.add_argument("--"+key,required=True)
    p.add_argument("--cutoff",required=True);a=p.parse_args()
    def read(path):return json.loads(Path(path).read_text())
    result=build(read(a.report),read(a.context),read(a.changes),read(a.goalies),read(a.special_teams),a.cutoff)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"inputs":len(result["games"]),"blocked":len(result["blocked_games"]),"calibrated":False}))
if __name__=="__main__":main()
