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
STATUS = re.compile(r"\b(Out|Doubtful|Questionable|Probable|Available|Injured Reserve)\b", re.I)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def parse_cbs(html, snapshot, observed):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for table in soup.find_all("table"):
        headers = " ".join(cell.get_text(" ", strip=True).lower() for cell in table.find_all("th"))
        if not any(k in headers for k in ("player", "injury", "status")):
            continue
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            text = " | ".join(cells)
            match = STATUS.search(text)
            if len(cells) >= 2 and match:
                rows.append({"raw_cells": cells, "raw_text": text,
                             "status_candidate": match.group(1).title(),
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
        if not title or len(title) < 12 or len(title) > 500 or not STATUS.search(title):
            continue
        href = node.get("href") if node.name == "a" else None
        link = urljoin(NBC_URL, href) if href else NBC_URL
        if title in seen:
            continue
        seen.add(title)
        items.append({"headline": title, "article_url": link, "source_url": NBC_URL,
                      "observed_at_utc": observed, "status_candidate": STATUS.search(title).group(1).title(),
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
            attempts.append({"source": source, "url": url, "status": "ok",
                             "candidate_count": len(candidates), "observed_at_utc": observed})
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
