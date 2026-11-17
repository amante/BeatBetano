"""Retry trusted NBA availability sources after the official NBA report fails.

Secondary sources remain explicitly non-official. This collector preserves
source, retrieval time and raw candidate evidence; it never promotes a media
claim to an official NBA status or changes frozen forecast probabilities.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

CBS_URL = "https://www.cbssports.com/nba/injuries/"
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
ESPN_PAGE = "https://www.espn.com/nba/injuries"
NBC_URL = "https://www.nbcsports.com/fantasy/basketball/player-news"
from injury_status_text import extract_status_candidate


def utcnow():
    return datetime.now(timezone.utc).isoformat()


CBS_TEAM_ALIASES = {
    "atlanta": "ATL", "atlanta hawks": "ATL",
    "boston": "BOS", "boston celtics": "BOS",
    "brooklyn": "BKN", "brooklyn nets": "BKN",
    "charlotte": "CHA", "charlotte hornets": "CHA",
    "chicago": "CHI", "chicago bulls": "CHI",
    "cleveland": "CLE", "cleveland cavaliers": "CLE",
    "dallas": "DAL", "dallas mavericks": "DAL",
    "denver": "DEN", "denver nuggets": "DEN",
    "detroit": "DET", "detroit pistons": "DET",
    "golden st": "GSW", "golden state": "GSW", "golden state warriors": "GSW",
    "houston": "HOU", "houston rockets": "HOU",
    "indiana": "IND", "indiana pacers": "IND",
    "la clippers": "LAC", "l a clippers": "LAC", "los angeles clippers": "LAC",
    "la lakers": "LAL", "l a lakers": "LAL", "los angeles lakers": "LAL",
    "memphis": "MEM", "memphis grizzlies": "MEM",
    "miami": "MIA", "miami heat": "MIA",
    "milwaukee": "MIL", "milwaukee bucks": "MIL",
    "minnesota": "MIN", "minnesota timberwolves": "MIN",
    "new orleans": "NOP", "new orleans pelicans": "NOP",
    "new york": "NYK", "new york knicks": "NYK",
    "oklahoma city": "OKC", "oklahoma city thunder": "OKC",
    "orlando": "ORL", "orlando magic": "ORL",
    "philadelphia": "PHI", "philadelphia 76ers": "PHI",
    "phoenix": "PHX", "phoenix suns": "PHX",
    "portland": "POR", "portland trail blazers": "POR",
    "sacramento": "SAC", "sacramento kings": "SAC",
    "san antonio": "SAS", "san antonio spurs": "SAS",
    "toronto": "TOR", "toronto raptors": "TOR",
    "utah": "UTA", "utah jazz": "UTA",
    "washington": "WAS", "washington wizards": "WAS",
}


def _cbs_team_code(label):
    key = re.sub(r"[^a-z0-9]+", " ", str(label or "").casefold()).strip()
    return CBS_TEAM_ALIASES.get(key)


def _cbs_table_team(table):
    # CBS renders a team heading immediately before its own player table.
    # Search nearby headings only; never infer a franchise from a player name.
    for heading in table.find_all_previous(["h2", "h3", "h4", "h5"], limit=8):
        code = _cbs_team_code(heading.get_text(" ", strip=True))
        if code:
            return code
    return None


def parse_cbs(html, snapshot, observed):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for table in soup.find_all("table"):
        headers = [re.sub(r"\s+", " ", cell.get_text(" ", strip=True).casefold()).strip()
                   for cell in table.find_all("th")]
        if not headers or not any(h in {"player", "name"} or "player" in h or "status" in h or "injury" in h
                                  for h in headers):
            continue
        player_index = next((i for i, h in enumerate(headers) if "player" in h or h == "name"), None)
        team_index = next((i for i, h in enumerate(headers) if h == "team" or h.endswith(" team")), None)
        # Prefer the explicit availability column. The prior parser selected the
        # earlier "Injury" column ("Knee", "Ankle") and dropped every real status.
        status_index = next((i for i, h in enumerate(headers)
                             if h in {"injury status", "status", "availability", "availability status"}), None)
        table_team = _cbs_table_team(table)
        for tr in table.find_all("tr"):
            cell_nodes = tr.find_all(["td", "th"])
            cells = [c.get_text(" ", strip=True) for c in cell_nodes]
            if not cells:
                continue
            text = " | ".join(cells)
            status_text = cells[status_index] if status_index is not None and status_index < len(cells) else text
            status_candidate = extract_status_candidate(status_text)
            if not status_candidate:
                continue
            player = None
            if player_index is not None and player_index < len(cell_nodes):
                player_cell = cell_nodes[player_index]
                linked_names = [a.get_text(" ", strip=True) for a in player_cell.find_all("a")
                                if a.get_text(" ", strip=True)]
                # CBS often includes an abbreviated link and a full-name link in
                # the same cell; use the longest attributed label for exact roster matching.
                player = max(linked_names, key=len) if linked_names else player_cell.get_text(" ", strip=True)
            team = cells[team_index] if team_index is not None and team_index < len(cells) else table_team
            team_code = _cbs_team_code(team) or team
            rows.append({"player_candidate": player, "team_candidate": team_code,
                         "team_label": team, "raw_cells": cells, "raw_text": text,
                         "status_candidate": status_candidate,
                         "source_url": CBS_URL, "observed_at_utc": observed,
                         "officially_verified": False})
    return rows

def parse_nbc(html, observed):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for node in soup.find_all(["a", "article"]):
        title = node.get("aria-label") or node.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", title).strip()
        status_candidate = extract_status_candidate(title)
        if not title or len(title) < 12 or len(title) > 500 or not status_candidate:
            continue
        href = node.get("href") if node.name == "a" else None
        link = urljoin(NBC_URL, href) if href else NBC_URL
        if title in seen:
            continue
        seen.add(title)
        items.append({"headline": title, "article_url": link, "source_url": NBC_URL,
                      "observed_at_utc": observed, "status_candidate": status_candidate,
                      "officially_verified": False, "editorial_claim": True})
    return items


def fetch(session, url):
    response = session.get(url, timeout=(10, 25), headers={"User-Agent": "Mozilla/5.0 (compatible; BeatBetano/1.0)"})
    response.raise_for_status()
    return response


def collect(snapshot, official, session=None):
    now = utcnow()
    s = session or requests.Session()
    results = []
    attempts = []
    # Sources are complementary: collect all structured provider reports on
    # every run, even when the official PDF is available, then capture NBC
    # editorial context separately. Never let one source erase another.
    for source, url, parser in (("CBS Sports", CBS_URL, "cbs"), ("ESPN", ESPN_URL, "espn")):
        observed = utcnow()
        try:
            response = fetch(s, url)
            if parser == "cbs":
                candidates = parse_cbs(response.text, snapshot, observed)
            else:
                from sporting_feed import extract as extract_espn
                data = extract_espn(response.json(), snapshot, observed)
                candidates = []
                for game_id, game in data.get("games", {}).items():
                    evidence = game.get("supplementary_injury_observations", {})
                    for row in evidence.get("items", []):
                        candidates.append({**row, "game_id": game_id, "source_url": ESPN_URL,
                                           "observed_at_utc": observed, "officially_verified": False})
            attempts.append({"source": source, "url": url,
                             "status": "ok" if candidates else "no_rows",
                             "candidate_count": len(candidates), "observed_at_utc": observed,
                             **({"detail": "Page responded but no injury-status rows were parsed; inspect source markup."}
                                if not candidates else {})})
            results.append({"source": source, "url": url, "source_type": "provider_injury_report",
                            "observed_at_utc": observed, "officially_verified": False,
                            "candidates": candidates})
        except Exception as exc:
            attempts.append({"source": source, "url": url, "status": "unavailable",
                             "error_type": type(exc).__name__, "detail": str(exc)[:500],
                             "observed_at_utc": observed})
    observed = utcnow()
    try:
        response = fetch(s, NBC_URL)
        candidates = parse_nbc(response.text, observed)
        attempts.append({"source": "NBC Sports Rotoworld", "url": NBC_URL, "status": "ok",
                         "candidate_count": len(candidates), "observed_at_utc": observed,
                         "source_type": "editorial_player_news"})
        results.append({"source": "NBC Sports Rotoworld", "url": NBC_URL,
                        "source_type": "editorial_player_news", "observed_at_utc": observed,
                        "officially_verified": False, "candidates": candidates})
    except Exception as exc:
        attempts.append({"source": "NBC Sports Rotoworld", "url": NBC_URL, "status": "unavailable",
                         "error_type": type(exc).__name__, "detail": str(exc)[:500],
                         "observed_at_utc": observed, "source_type": "editorial_player_news"})
    return {"retrieval_mode": "multi_source_complement",
            "official_source": official.get("report_url"),
            "official_source_available": official.get("official_document_retrieved") is True,
            "official_source_error": official.get("retrieval_error_detail") or official.get("retrieval_http_status"),
            "observed_at_utc": now, "attempts": attempts, "sources": results,
            "officially_verified": False,
            "probability_adjustment_authorized": False,
            "note": "The NBA PDF has official provenance. CBS and ESPN are separate provider observations; NBC is editorial context. Identity, team, time and conflicts must be reconciled before modeling."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--official", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = collect(json.loads(Path(args.snapshot).read_text()), json.loads(Path(args.official).read_text()))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))
    print(json.dumps({"mode": result["retrieval_mode"], "sources_attempted": len(result.get("attempts", [])),
                      "candidate_count": sum(len(x.get("candidates", [])) for x in result.get("sources", [])),
                      "officially_verified": result.get("officially_verified", True)}, indent=2))


if __name__ == "__main__":
    main()
