"""Assemble strictly pregame, source-linked input bundles for NHL joint engine #320."""
import argparse, hashlib, json, math
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from nhl.pulso_goalie_multisource_257 import TEAM_NAMES, norm
from nhl.division_rivalry import estimate as estimate_division_rivalry, load_history as load_division_history

API = "https://api.nhle.com/stats/rest/en"

def blocker_category(reason):
    """Report captured projections separately from unavailable lineup sources."""
    text = str(reason).lower()
    if "projected lines captured but player identity unresolved" in text:
        return "lineup_identity_partial"
    if "projected lineup not captured" in text:
        return "lineup_source_missing"
    # Keep the established category for structural/incomplete evidence while
    # giving the user a more precise display status below.
    if "lineup evidence incomplete" in text or "projected" in text and ("incomplete" in text or "missing" in text):
        return "lineup_not_confirmed"
    return "other_input_unavailable"

def utc(value):
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None: raise ValueError("Source timestamps must include timezone")
    return d.astimezone(timezone.utc)

def season_for(day):
    y, m = int(day[:4]), int(day[5:7]); start = y if m >= 7 else y - 1
    return f"{start}{start+1}"

def get_json(url):
    try:
        with urlopen(Request(url, headers={"Accept":"application/json", "User-Agent":"PULSO-NHL-joint/1.0"}), timeout=25) as r:
            raw = r.read(8_000_001)
            if len(raw) > 8_000_000: raise ValueError("Oversized official source")
    except HTTPError as error:
        details=error.read(4096).decode("utf-8","replace").replace("\n"," ")[:1000]
        raise ValueError(f"NHL Stats API HTTP {error.code} for {url}: {details}") from error
    return json.loads(raw), {"url":url,"sha256":hashlib.sha256(raw).hexdigest(),"retrieved_at_utc":datetime.now(timezone.utc).isoformat()}

def stat_rows(resource, season, cutoff, sort="playerId:ASC"):
    # These are season-summary tables, not per-game rows; gameDate is not a
    # valid dimension here. Keep the fixture cutoff by the source timestamp
    # gate in build(): every included game's start must be after every query.
    date.fromisoformat(cutoff)
    sort_field, separator, direction=sort.rpartition(":")
    if not separator or not sort_field.replace("_","").isalnum() or direction not in ("ASC","DESC"):
        raise ValueError("Invalid NHL Stats sort specification")
    sort_value=json.dumps([{"property":sort_field,"direction":direction}],separators=(",",":"))
    rows=[];start=0;total=None; sources=[]
    while total is None or start < total:
        q=urlencode({"isAggregate":"false","isGame":"false","start":start,"limit":100,"sort":sort_value,"cayenneExp":f'seasonId={season} and gameTypeId=2'})
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

def toi(value, *, allow_missing=False, label="TOI"):
    # NHL stats can return null for zero PP/PK usage. When EV alone is null,
    # player_record derives it from the official total minus PP and PK TOI.
    # Total TOI remains required; no missing total is imputed.
    if value is None or (isinstance(value, str) and not value.strip()):
        if allow_missing:
            return 0.0
        raise ValueError("Missing NHL time-on-ice value for " + label)
    if type(value) in (float,int) and math.isfinite(value) and value>=0:
        return value/60 if value>100 else value
    if isinstance(value,str):
        value=value.strip()
        if ":" in value:
            mm,ss=value.split(":",1)
            if mm.isdigit() and ss.isdigit() and int(ss)<60:return int(mm)+int(ss)/60
        elif value.isdigit():
            numeric=int(value)
            return numeric/60 if numeric>100 else float(numeric)
    raise ValueError("Invalid NHL time-on-ice value for " + label + ": " + repr(value))

def build(report, context, changes, goalies, special, cutoff, division_history=None, division_history_source=None, return_to_play=None, rotowire=None):
    fixtures={str(g["game_id"]):g for g in report.get("games",[])}
    if len(fixtures)!=len(report.get("games",[])): raise ValueError("Duplicate schedule fixture")
    if context.get("kind")!="nhl_pregame_player_evidence_v1" or changes.get("kind")!="nhl_projected_lineup_changes_v1": raise ValueError("Wrong lineup evidence contract")
    if goalies.get("kind")!="nhl_all_goalie_candidates_history_260": raise ValueError("Wrong goalie history contract")
    day=date.fromisoformat(cutoff); season=season_for(cutoff)
    return_by_game={}
    if (isinstance(return_to_play,dict) and return_to_play.get("kind")=="nhl_return_to_play_v1"
            and return_to_play.get("date")==cutoff):
        return_by_game={str(item.get("game_id")):item for item in return_to_play.get("games",[])
                        if isinstance(item,dict) and item.get("game_id") is not None}
    rotowire_by_game={}
    if rotowire is not None:
        if (rotowire.get("kind")!="nhl_rotowire_reconciled_pregame_v475"
                or rotowire.get("official") is not False
                or rotowire.get("probabilities_modified") is not False):
            raise ValueError("Wrong RotoWire evidence contract")
        rotowire_by_game={str(item.get("game_id")):item for item in rotowire.get("games",[])
                          if isinstance(item,dict) and item.get("game_id") is not None}
        if len(rotowire_by_game)!=len(rotowire.get("games",[])):
            raise ValueError("Duplicate RotoWire fixture")
    if division_history is None:
        history_path=Path(__file__).resolve().parents[1]/"reports/nhl/goalie-candidate-2026-11-02/evidence/labels.csv"
        if history_path.is_file():
            division_history,division_history_source=load_division_history(history_path)
        else:
            division_history,division_history_source=[],None
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
        pp=toi(t.get("powerPlayTimeOnIcePerGame"),allow_missing=True,label="PP")
        pk=toi(t.get("shorthandedTimeOnIcePerGame"),allow_missing=True,label="PK")
        total=toi(t.get("timeOnIcePerGame"),label="total")
        raw_ev=t.get("evenStrengthTimeOnIcePerGame")
        if raw_ev is None or (isinstance(raw_ev,str) and not raw_ev.strip()):
            ev=total-pp-pk
            if ev < -1.5:
                raise ValueError("Cannot derive EV TOI from official total, PP and PK values for "+str(person.get("name")))
            ev=max(0.0,ev)
            ev_source="derived_official_total_minus_PP_and_PK"
        else:
            ev=toi(raw_ev,label="EV")
            ev_source="official_even_strength_time_on_ice_per_game"
        minutes={"EV":ev,"PP":pp,"PK":pk}
        minute_sources={"EV":ev_source,"PP":"official_power_play_time_on_ice_per_game_or_explicit_zero",
                        "PK":"official_shorthanded_time_on_ice_per_game_or_explicit_zero"}
        prod={k:number(s,k) for k in ("goals","assists","shots","penaltyMinutes","evGoals","ppGoals","shGoals","evPoints","ppPoints","shPoints")}
        return {"player_id":int(pid),"name":person.get("name") or s.get("skaterFullName"),"team_abbrevs":code,"position":s.get("positionCode"),"availability":"active","games_played":gp,"minutes_per_game":minutes,"minutes_per_game_sources":minute_sources,"total_minutes_per_game":total,"production":prod}
    for gid,f in fixtures.items():
        start=utc(f["start_utc"])
        if start <= observed or start <= utc(report["generated_at_utc"]): continue
        for captured_at in (context.get("as_of_utc"), changes.get("as_of_utc", report["generated_at_utc"]), goalies.get("as_of_utc"), special.get("as_of_utc")):
            if captured_at and utc(captured_at) >= start: raise ValueError("Pregame evidence captured after puck drop")
        try:
            cg=context_games.get(gid); lg=change_games.get(gid); gg=goalie_games.get(gid); rg=rotowire_by_game.get(gid)
            game_fallback_reasons=[]
            if not cg or (cg.get("home"),cg.get("away"))!=(f["home"],f["away"]):
                cg={"home":f["home"],"away":f["away"],"teams":{}}
                game_fallback_reasons.append("No hay captura de alineaciones identificable para este partido.")
            if not gg or (gg.get("home"),gg.get("away")) not in ((None,None),(f["home"],f["away"])):
                gg={"teams":{}}
                game_fallback_reasons.append("No hay historial individual verificable de porteros.")
            if lg and (lg.get("home"),lg.get("away")) not in ((None,None),(f["home"],f["away"])):
                lg=None
                game_fallback_reasons.append("La comparación de alineaciones corresponde a otro partido.")
            if rg and ((rg.get("home"),rg.get("away"))!=(f["home"],f["away"])
                       or rg.get("start_utc")!=f["start_utc"]):
                raise ValueError("RotoWire fixture identity mismatch")
            if rg and rg.get("source",{}).get("captured_at_utc") and utc(rg["source"]["captured_at_utc"])>=start:
                raise ValueError("late RotoWire evidence")
            change_teams=(lg or {}).get("teams",{})
            sides={};unknown=[]
            editorial_source=cg.get("editorial_source")
            if not editorial_source or not editorial_source.get("sha256") or not editorial_source.get("url") or not cg.get("feature_as_of_utc"):
                game_fallback_reasons.append("No hay procedencia editorial fechada para validar líneas.")
            for code in (f["home"],f["away"]):
                side=cg["teams"].get(code) or {}; diff=change_teams.get(code); teamrow=team_by_code.get(code); sp=special.get("teams",{}).get(code)
                groups=side.get("projected")
                if not isinstance(groups,dict):
                    groups={}
                lineup_conflict=bool(side.get("availability_conflict"))
                lineup_missing=lineup_conflict or not (groups.get("forwards") or groups.get("defense"))
                fallback_reasons=list(game_fallback_reasons)
                if lineup_conflict: fallback_reasons.append("La proyección de líneas contradice el reporte de disponibilidad.")
                if lineup_missing: fallback_reasons.append("No hay alineación proyectada identificable.")
                coverage=side.get("projected_skaters_identity_coverage",{})
                projected_partial=(lineup_missing or not bool(side.get("projected_skaters_identity_complete"))
                                   or not groups.get("forwards") or not groups.get("defense"))
                unresolved_names=list(coverage.get("unresolved_names",[]))
                if lineup_missing:
                    unknown.append(code+" projected lineup missing or contradictory; team aggregate fallback; player props and lineup effects omitted")
                    diff={"new_in_projection":[],"out_of_projection":[]}
                if not diff or diff.get("status")!="projected_changes_observed_not_calibrated":
                    fallback_reasons.append("No hay comparación verificable con la alineación anterior.")
                    if not lineup_missing: unknown.append(code+" prior-lineup comparison unavailable; no removals inferred")
                    diff={"new_in_projection":[],"out_of_projection":[]}
                if projected_partial:
                    if not unresolved_names:
                        unresolved_names=[
                            person.get("name")
                            for group_name in ("forwards","defense")
                            for row in (groups.get(group_name) or [])
                            for person in row
                            if not person.get("identity_resolved")
                        ]
                    if unresolved_names:
                        unknown.append(code+" projected skaters excluded (identity unresolved): "+", ".join(str(name) for name in unresolved_names[:12]))
                    if lineup_missing or not diff or diff.get("status")!="projected_changes_observed_not_calibrated":
                        if not lineup_missing:
                            unknown.append(code+" prior-lineup comparison unavailable; no removals inferred")
                        diff={"new_in_projection":[],"out_of_projection":[]}
                if not teamrow: raise ValueError(code+" official team stats unavailable")
                if not sp:
                    fallback_reasons.append("Faltan estadísticas oficiales de PP/PK para "+code+".")
                    sp={"games_played":0,"powerplay_goals":0,"powerplay_opportunities":0,"opponent_powerplay_goals":0,"times_shorthanded":0}
                elif number(sp,"powerplay_opportunities")<=0 or number(sp,"times_shorthanded")<=0:
                    fallback_reasons.append("La muestra oficial de PP/PK está incompleta para "+code+".")
                lines=[]
                coverage_counts={}
                for unit,field in (("forwards","forwards"),("defense","defense")):
                    raw=groups.get(field)
                    expected=12 if unit=="forwards" else 6
                    if not isinstance(raw,list) or len(raw)!=(4 if unit=="forwards" else 3):
                        fallback_reasons.append("La proyección de "+field+" está incompleta.")
                        raw=[]
                    resolved_count=sum(1 for line in raw for person in line if person.get("identity_resolved") and person.get("player_id") is not None)
                    coverage_counts[unit]=dict(expected=expected,captured=sum(len(line) for line in raw),resolved=resolved_count,
                                                       ev_toi_derived=sum(1 for line in raw for person in line if person.get("identity_resolved") and person.get("player_id") is not None and player.get(str(person.get("player_id"))) and toi_by_id.get(str(person.get("player_id"))) and (toi_by_id[str(person.get("player_id"))].get("evenStrengthTimeOnIcePerGame") is None or not str(toi_by_id[str(person.get("player_id"))].get("evenStrengthTimeOnIcePerGame")).strip())))
                    if coverage_counts[unit]["captured"] < expected:
                        fallback_reasons.append("Faltan plazas de "+unit+" en la alineación capturada.")
                        unknown.append(code+" "+unit+" projected slots not captured: "+str(expected-coverage_counts[unit]["captured"]))
                    def safe_player_record(person,reason):
                        try:
                            return player_record(person,code)
                        except (KeyError,TypeError,ValueError) as error:
                            fallback_reasons.append("Hay jugadores sin estadísticas individuales atribuibles con certeza.")
                            unknown.append(code+" "+reason+" excluded for "+str(person.get("name") or person.get("player_id"))+": "+str(error)[:140])
                            return None
                    if unresolved_names:
                        fallback_reasons.append("Hay identidades de jugadores de la alineación sin resolver.")
                    for i,line in enumerate(raw,1):
                        resolved=[person for person in line if person.get("identity_resolved") and person.get("player_id") is not None]
                        modeled=[record for record in (safe_player_record(person,"projected player history") for person in resolved) if record]
                        lines.append({"unit":unit,"line":i,"players":modeled})
                if not any(item["players"] for item in lines) and not lineup_missing:
                    unknown.append(code+" projected lineup has no resolved identities; using team aggregate baseline only; player props and lineup-specific effects omitted")
                    fallback_reasons.append("No hay identidades de patinadores utilizables.")
                    lineup_missing=True
                    diff={"new_in_projection":[],"out_of_projection":[]}
                captured_ids={person["player_id"] for line in lines for person in line["players"]}
                incoming=[]
                for x in diff.get("new_in_projection",[]):
                    if x.get("player_id") in captured_ids:
                        record=safe_player_record({"player_id":x.get("player_id"),"name":x.get("name")},"incoming player history")
                        if record: incoming.append(record)
                    else:
                        unknown.append(code+" incoming skater omitted from adjustment; absent from identified projected lines: "+str(x.get("name") or x.get("player_id")))
                outgoing=[]
                for x in diff.get("out_of_projection",[]):
                    p=safe_player_record({"player_id":x.get("player_id"),"name":x.get("name")},"outgoing player history")
                    if p: p["position"]="D" if x.get("position_group")=="defense" else "F";outgoing.append(p)
                absent=[]
                injured_goalie_ids=set()
                for field in ("injuries","scratches"):
                    names=groups.get(field)
                    if names is None:
                        fallback_reasons.append("Falta la captura de "+field+" para confirmar disponibilidad.")
                        unknown.append(code+" "+field+" source missing"); continue
                    for person in names:
                        if not person.get("identity_resolved"):
                            fallback_reasons.append("Hay una baja o ausencia sin identidad verificable.")
                            unknown.append(code+" unresolved "+field+": "+str(person.get("name"))); continue
                        pid=person.get("player_id")
                        is_goalie=str(person.get("position") or person.get("position_code") or "").strip().upper() in ("G","GOALIE")
                        if field=="injuries" and pid is not None and (is_goalie or str(pid) in {str(g.get("player_id")) for g in gg.get("teams",{}).get(code,[])} or (str(pid),code) in goalie_rows_by_identity):
                            injured_goalie_ids.add(str(pid))
                            unknown.append(code+" goalie injury excluded from skater availability: "+str(person.get("name")))
                            fallback_reasons.append("Se detectó una baja de portero; no se atribuye como baja de patinador.")
                            continue
                        p=safe_player_record(person,field+" player history")
                        if p: p["availability"]="injury" if field=="injuries" else "scratch";absent.append(p)
                candidates=gg.get("teams",{}).get(code,[]);glist=[]
                team_games=number(teamrow,"gamesPlayed",True)
                for g in candidates:
                    try:
                        if g.get("status")!="observed": raise ValueError("history unavailable")
                        pid=str(g["player_id"])
                        if pid in injured_goalie_ids: continue
                        stat_rows_for_goalie=goalie_rows_by_identity.get((pid,code),[])
                        if len(stat_rows_for_goalie)>1: raise ValueError("duplicate goalie start history")
                        games_started=number(stat_rows_for_goalie[0],"gamesStarted") if stat_rows_for_goalie else 0
                        if games_started>team_games: raise ValueError("goalie starts exceed team games")
                        goalie_stats=g["metrics"]["season_to_date"]
                        glist.append({"player_id":g["player_id"],"name":g["name"],"status":"observed","candidate_status":g.get("candidate_status"),"independently_confirmed_starter":False,"games_started_before_cutoff":games_started,"team_games_played_before_cutoff":team_games,"metrics":{"season_to_date":{"shots_against":goalie_stats["shots_against"],"saves":goalie_stats["saves"]}}})
                    except (KeyError,TypeError,ValueError) as error:
                        fallback_reasons.append("Falta historial individual verificable de un portero.")
                        unknown.append(code+" goalie candidate omitted: "+str(error)[:120])
                if not glist:
                    shots_against=number(teamrow,"shotsAgainstPerGame",True)
                    goals_against=number(teamrow,"goalsAgainstPerGame")
                    saves_per_game=shots_against-goals_against
                    if saves_per_game<0: raise ValueError(code+" invalid team aggregate goalie proxy")
                    glist=[{"player_id":None,"name":"Promedio defensivo del equipo (sin portero identificado)","status":"observed","candidate_status":"team_aggregate_save_rate_proxy","independently_confirmed_starter":False,"games_started_before_cutoff":0,"team_games_played_before_cutoff":team_games,"starter_probability":None,"metrics":{"season_to_date":{"shots_against":shots_against,"saves":saves_per_game}}}]
                    fallback_reasons.append("Se usa la tasa defensiva oficial como referencia de portería, sin atribuirla a un jugador.")
                candidate_starts=sum(g["games_started_before_cutoff"] for g in glist)
                complete_start_coverage=(candidate_starts==team_games)
                for g in glist:
                    g["starter_probability"]=g["games_started_before_cutoff"]/team_games if complete_start_coverage else None
                goalie_start_distribution={"status":"complete_empirical_share" if complete_start_coverage else "incomplete_candidate_coverage","method":"candidate_games_started_divided_by_team_games_played","team_games_played":team_games,"candidate_starts":candidate_starts,"probabilities_sum_to_one":complete_start_coverage}
                if groups.get("injuries") is None or groups.get("scratches") is None:
                    fallback_reasons.append("El reporte de disponibilidad está incompleto.")
                    unknown.append(code+" incomplete availability report")
                exact=[r for r in skaters if r.get("teamAbbrevs")==code]
                multi=[r for r in skaters if code in str(r.get("teamAbbrevs","")).split(",") and r.get("teamAbbrevs")!=code]
                if multi:
                    fallback_reasons.append("Hay estadísticas de jugadores transferidos que no se pueden atribuir al equipo actual.")
                    unknown.append(code+" multi-team player statistics excluded from individual attribution")
                totals={k:sum(number(r,k) for r in exact) for k in ("goals","assists","shots","penaltyMinutes","evGoals","evPoints","ppGoals","ppPoints","shGoals","shPoints")}
                # Keep a full, identity-safe team skater pool for the aggregate
                # fallback. RotoWire's PP units can then affect the experimental
                # goal rate even when 5v5 line combinations are unavailable.
                team_roster_skaters=[]
                for stats_row in skaters:
                    if stats_row.get("teamAbbrevs")!=code or str(stats_row.get("positionCode","")).upper()=="G":
                        continue
                    person={"player_id":stats_row.get("playerId"),"name":stats_row.get("skaterFullName")}
                    try:
                        team_roster_skaters.append(player_record(person,code))
                    except (KeyError,TypeError,ValueError):
                        continue
                gp=number(teamrow,"gamesPlayed",True)
                modeled_count=sum(len(line["players"]) for line in lines)
                projected_slots=sum(item["expected"] for item in coverage_counts.values())
                aggregate_only=bool(fallback_reasons) or lineup_missing or modeled_count==0
                sides[code]={"projected_lines":lines,
                    "lineup_coverage":{"partial":aggregate_only or modeled_count<projected_slots,"mode":"team_aggregate_fallback" if aggregate_only else ("identified_partial_lineup" if modeled_count<projected_slots else "projected_lineup"),
                        "fallback_reasons":list(dict.fromkeys(fallback_reasons)),
                        "expected_skaters":projected_slots,
                        "captured_skaters":sum(item["captured"] for item in coverage_counts.values()),
                        "modeled_skaters":modeled_count,"ev_toi_derived_player_count":sum(item["ev_toi_derived"] for item in coverage_counts.values()),
                        "excluded_names":unresolved_names,"by_unit":coverage_counts},
                    "lineup_changes":{"new_in_projection":incoming,"out_of_projection":outgoing},
                    "unavailable_players":absent,"goalie_candidates":glist,"goalie_start_distribution":goalie_start_distribution,
                    "team_summary":teamrow,"special_teams":{"games_played":sp["games_played"],"powerplay_goals":sp["powerplay_goals"],"powerplay_opportunities":sp["powerplay_opportunities"],"opponent_powerplay_goals":sp["opponent_powerplay_goals"],"times_shorthanded":sp["times_shorthanded"]},
                    "team_roster_penalty_minutes":{"total":totals["penaltyMinutes"],"games_played":gp,"unattributed_multi_team_players":len(multi)},
                    "team_roster_production":{"player_rows":len(exact),"games_played":gp,"totals":totals,"unattributed_multi_team_players":len(multi)},"team_roster_skaters":team_roster_skaters,
                    "rotowire_pregame":(rg.get("teams",{}).get(code) if rg else None),
                    "rotowire_market_observation":(rg.get("market_observation") if rg else None),
                    "rotowire_source":(rg.get("source") if rg else None),
                    "schedule":{},"_unknown":unknown}
            if any(sides[code]["lineup_coverage"]["mode"]=="team_aggregate_fallback" for code in sides):
                combined_reasons=list(dict.fromkeys(reason for side in sides.values() for reason in side["lineup_coverage"].get("fallback_reasons",[])))
                for code,side in sides.items():
                    side["projected_lines"]=[]
                    side["lineup_changes"]={"new_in_projection":[],"out_of_projection":[]}
                    side["unavailable_players"]=[]
                    side["lineup_coverage"].update({"partial":True,"mode":"team_aggregate_fallback","modeled_skaters":0,"fallback_reasons":combined_reasons})
                unknown.extend(combined_reasons)
            return_game=return_by_game.get(gid,{})
            return_teams=return_game.get("teams",{}) if isinstance(return_game,dict) else {}
            for code in (f["home"],f["away"]):
                return_team=return_teams.get(code,{})
                if not return_team or not isinstance(return_team,dict) or not isinstance(return_team.get("players",{}),dict):
                    return_team={"status":"source_unavailable","players":{},"source_manifest":[]}
                sides[code]["return_to_play"]=return_team
            cutoff_for_engine=cutoff
            if date.fromisoformat(cutoff_for_engine)>=start.date(): raise ValueError("source cutoff is not strictly before fixture UTC date")
            captured=datetime.now(timezone.utc)
            if captured>=start: raise ValueError("Assembly completed after puck drop")
            manifest=s1+s2+s3+s4+s5+s6
            if rg and rg.get("source",{}).get("url") and rg.get("source",{}).get("page_sha256"):
                stamp=utc(rg["source"].get("captured_at_utc"))
                if stamp>=start: raise ValueError("late RotoWire source")
                manifest.append({"url":rg["source"]["url"],"sha256":rg["source"]["page_sha256"],"retrieved_at_utc":stamp.isoformat(),"provider":"RotoWire","source_role":"primary_pregame_observation"})
            for code in (f["home"],f["away"]):
                for source in sides[code].get("return_to_play",{}).get("source_manifest",[]):
                    stamp=source.get("retrieved_at_utc") or source.get("retrieved_at")
                    if stamp and source.get("url"):
                        retrieved=utc(stamp)
                        if retrieved<start:
                            manifest.append({"url":source["url"],"sha256":source.get("sha256"),
                                             "retrieved_at_utc":retrieved.isoformat()})
            editor=cg.get("editorial_source")
            if editor and editor.get("sha256") and editor.get("url") and cg.get("feature_as_of_utc"):
                editorial_at=utc(cg["feature_as_of_utc"])
                if editorial_at>=start: raise ValueError("late editorial lineup capture")
                manifest.append({"url":editor["url"],"sha256":editor["sha256"],"retrieved_at_utc":editorial_at.isoformat()})
            for source in special.get("sources",[]):
                stamp=source.get("retrieved_at_utc") or source.get("retrieved_at")
                if stamp:
                    if utc(stamp)>=start: raise ValueError("late special-team source")
                    manifest.append({"url":source.get("url"),"sha256":source.get("sha256"),"retrieved_at_utc":utc(stamp).isoformat()})
            for code in (f["home"],f["away"]):
                ref=(change_games.get(gid) or {}).get("teams",{}).get(code,{}).get("reference_source")
                if ref and ref.get("retrieved_at"):
                    if utc(ref["retrieved_at"])>=start: raise ValueError("late prior-lineup reference")
                    manifest.append({"url":ref.get("url"),"sha256":ref.get("sha256"),"retrieved_at_utc":utc(ref["retrieved_at"]).isoformat()})
            # In team-aggregate mode, incomplete PP/PK counts are an explicit
            # omission; the aggregate baseline does not consume those rates.
            goalie_sources=[]
            for code in (f["home"],f["away"]):
                for g in (goalie_games.get(gid) or {}).get("teams",{}).get(code,[]):
                    if g.get("status")=="observed":
                        meta=g.get("source",{}); stamp=utc(meta.get("retrieved_at", ""))
                        if stamp>=start: raise ValueError("post-start goalie statistics")
                        goalie_sources.append({"url":meta.get("url"),"sha256":meta.get("sha256"),"retrieved_at_utc":stamp.isoformat()})
            manifest+=goalie_sources
            if any(utc(x["retrieved_at_utc"])>=start for x in manifest): raise ValueError("Post-start source")
            division_rivalry=estimate_division_rivalry(f["home"],f["away"],cutoff_for_engine,division_history,division_history_source)
            output.append({"kind":"nhl_joint_match_inputs_v1","game_id":gid,"home":f["home"],"away":f["away"],"start_utc":f["start_utc"],"cutoff_exclusive":cutoff_for_engine,"captured_at_utc":captured.isoformat(),"poststart_reconstruction":False,"league_context":{"powerplay_goals_allowed_per_opportunity":league_pk_rate},"division_rivalry":division_rivalry,"teams":sides,"unknowns":unknown,"source_manifest":manifest})
        except (KeyError,TypeError,ValueError) as e:
            reason=str(e)[:240]
            category=blocker_category(reason)
            blocked.append({"game_id":gid,"home":f["home"],"away":f["away"],
                            "category":category,
                            "status":("Proyección capturada; faltan identidades" if category=="lineup_identity_partial" else
                                      "Fuente de alineaciones no disponible" if category=="lineup_source_missing" else
                                      "Proyección de alineación incompleta" if category=="lineup_not_confirmed" else
                                      "Escenario integrado pendiente"),
                            "reason":reason})
    return {"kind":"nhl_joint_match_input_batch_v321","date":cutoff,"season":season,"generated_at_utc":datetime.now(timezone.utc).isoformat(),"games":output,"blocked_games":blocked,"official":False,"calibrated":False,"odds_used":False}

def main():
    p=argparse.ArgumentParser()
    for key in ("report","context","changes","goalies","special-teams","output"):p.add_argument("--"+key,required=True)
    p.add_argument("--cutoff",required=True);p.add_argument("--return-to-play");p.add_argument("--rotowire");a=p.parse_args()
    def read(path):return json.loads(Path(path).read_text())
    return_data=read(a.return_to_play) if a.return_to_play else None
    rotowire_data=read(a.rotowire) if a.rotowire else None
    result=build(read(a.report),read(a.context),read(a.changes),read(a.goalies),read(a.special_teams),a.cutoff,
                 return_to_play=return_data,rotowire=rotowire_data)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"inputs":len(result["games"]),"blocked":len(result["blocked_games"]),"calibrated":False}))
if __name__=="__main__":main()
