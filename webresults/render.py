"""Render NHL/NBA pregame JSON as a standalone accessible HTML dashboard and Actions summary."""
import argparse,html,json,os
from pathlib import Path

def fmt(p):
    return "—" if p is None else f"{100*float(p):.1f}%"

def build(report):
    sport=str(report.get("sport","")).lower()
    if sport not in ("nhl","nba"):raise ValueError("NHL/NBA report required")
    games=report.get("events" if sport=="nhl" else "games")
    if not isinstance(games,list):raise ValueError("Missing games")
    rows=[];markdown=[]
    for game in games:
        home=game.get("home_team");away=game.get("away_team")
        if not home or not away:raise ValueError("Missing teams")
        p=game.get("statistical_p_home") if sport=="nhl" else game.get("statistical_baseline_home")
        if p is None and sport=="nba":p=game.get("hybrid_baseline_p_home")
        if p is not None and (type(p) not in (int,float) or not 0<p<1):raise ValueError("Invalid probability")
        tip=game.get("start_utc",game.get("tipoff_utc",""))
        status=game.get("status","preliminary_not_validated")
        rows.append((str(tip),str(away),str(home),fmt(1-p) if p is not None else "—",fmt(p),str(status)))
    rows.sort()
    esc=lambda x:html.escape(str(x),quote=True)
    tr="".join("<tr>"+ "".join(f"<td>{esc(v)}</td>" for v in r)+"</tr>" for r in rows)
    asof=report.get("as_of_utc",report.get("date","Sin fecha"))
    label=sport.upper()
    page=f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{label} hoy | BeatBetano</title>
<style>
:root{{--bg:#0b1220;--surface:#17243a;--ink:#eef5ff;--muted:#b4c4db;--accent:#7ed4ea}}
*{{box-sizing:border-box}}body{{font:16px system-ui,sans-serif;margin:0;background:var(--bg);color:var(--ink);line-height:1.5}}
main{{width:min(1180px,94%);margin:40px auto}}header{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}}
h1{{font-size:clamp(26px,5vw,42px);margin-bottom:4px}}p{{color:var(--muted)}}
small{{color:var(--muted)}}.meta{{background:var(--surface);padding:18px;border-radius:14px;margin:20px 0}}
table{{border-collapse:collapse;width:100%;min-width:760px}}th,td{{padding:13px;text-align:left;border-bottom:1px solid #304158}}
th{{color:var(--accent)}}.table{{overflow:auto;background:var(--surface);border-radius:14px}}
input{{background:var(--surface);color:var(--ink);padding:12px;border:1px solid #526b86;border-radius:8px;width:min(360px,100%)}}
mark{{color:inherit;background:#315064}}
</style></head><body><main>
<header><div><h1>{label} hoy</h1><small>BeatBetano · {esc(asof)}</small></div><input id="filter" aria-label="Filtrar equipos" placeholder="Buscar equipo..." oninput="filterRows()"></header>
<div class="meta"><strong>{len(rows)} partidos pregame registrados</strong><p>Probabilidades estadísticas <b>preliminares, no calibradas</b>. No incluyen verificación completa de arqueros/quintetos, bajas ni validación independiente. No son apuestas recomendadas.</p></div>
<section class="table" aria-label="Cartelera"><table><thead><tr><th>Inicio UTC</th><th>Visitante</th><th>Local</th><th>P(visitante)</th><th>P(local)</th><th>Estado</th></tr></thead><tbody id="games">{tr}</tbody></table></section>
<p>Sin cuotas como entrada. Las estimaciones pueden cambiar si se verifican datos deportivos nuevos; no se modifican pronósticos congelados retrospectivamente.</p></main>
<script>function filterRows(){{const q=document.getElementById('filter').value.toLowerCase();for(const row of document.querySelectorAll('#games tr'))row.hidden=!row.textContent.toLowerCase().includes(q);}}</script></body></html>"""
    markdown=[f"## {label} hoy — {asof}", "", "**Estimaciones preliminares, no calibradas; ninguna apuesta autorizada.**", "",
              "| Inicio UTC | Visitante | Local | P(visitante) | P(local) |", "|---|---|---|---:|---:|"]
    markdown += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |" for r in rows]
    markdown+=["",f"**Total:** {len(rows)} partidos. El HTML está disponible como artefacto de esta ejecución."]
    return page,"\n".join(markdown)+"\n"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True);ap.add_argument("--html",required=True);ap.add_argument("--summary",required=True)
    args=ap.parse_args()
    page,summary=build(json.loads(Path(args.input).read_text()))
    for path,text in [(args.html,page),(args.summary,summary)]:
        out=Path(path);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a") as f:f.write(summary)
    print(f"Dashboard written: {args.html}")
if __name__=="__main__":main()
