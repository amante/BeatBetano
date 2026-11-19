"""Capture and validate dated RotoWire NHL pregame cards.

The public page is treated as an observation source, not as official NHL data.
The capture preserves a source snapshot and parses pregame observations by
fixture, including lineups, statuses, and visible market fields. RotoWire is a
primary pregame observation source; official NHL fixtures remain the identity
anchor. This capture does not modify model probabilities.
"""
import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

URL = "https://www.rotowire.com/hockey/nhl-lineups.php"
MAX_BYTES = 8_000_000


class Node:
    def __init__(self, tag, attrs=(), parent=None):
        self.tag = tag
        self.attrs = dict(attrs)
        self.classes = set(self.attrs.get("class", "").split())
        self.parent = parent
        self.children = []
        self.parts = []
        self.content = []

    def text(self):
        ordered = [item if isinstance(item, str) else item.text() for item in self.content]
        return " ".join(" ".join(ordered).split())

    def descendants(self):
        for child in self.children:
            yield child
            yield from child.descendants()

    def has_class(self, value):
        return value in self.classes


class DocumentParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("document")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        self.stack[-1].content.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        self.stack[-1].content.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        if self.stack:
            self.stack[-1].parts.append(data)
            self.stack[-1].content.append(data)


def fetch(url=URL, opener=urlopen):
    if url != URL:
        raise ValueError("Unexpected RotoWire URL")
    request = Request(url, headers={
        "User-Agent": "BeatBetano-PULSO/1.0",
        "Accept": "text/html",
    })
    with opener(request, timeout=25) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("RotoWire page exceeds capture size limit")
    return raw, {
        "source_url": url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _find_all(root, predicate):
    return [node for node in root.descendants() if predicate(node)]


def _abbr(team_node):
    nodes = _find_all(team_node, lambda n: n.has_class("lineup__abbr"))
    value = nodes[0].text().strip().upper() if len(nodes) == 1 else ""
    return value if re.fullmatch(r"[A-Z]{2,3}", value) else None



STATUS_RE = re.compile(r"\b(CONFIRMED|LIKELY|EXPECTED|DTD|OUT|IR-LT|IR-NR|IR)\b", re.I)
POSITION_RE = re.compile(r"\b(C|LW|RW|LD|RD|G)\b", re.I)


def _player_observations(container):
    observations = []
    for anchor in _find_all(container, lambda n: n.tag == "a"):
        name = anchor.text().strip()
        if not name or len(name) > 80:
            continue
        row = anchor
        parent = anchor.parent
        while parent is not None and parent is not container:
            if parent.tag in {"li", "tr"}:
                row = parent
                break
            parent = parent.parent
        row_text = row.text()
        status = STATUS_RE.search(row_text)
        position = POSITION_RE.search(row_text)
        observations.append({
            "name": name,
            "href": anchor.attrs.get("href"),
            "position_observation": position.group(1).upper() if position else None,
            "status_observation": status.group(1).upper() if status else None,
            "row_text": row_text[:240],
        })
    unique, seen = [], set()
    for item in observations:
        key = (item["name"], item["href"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _class_observation(container, pattern):
    nodes = _find_all(container, lambda n: any(pattern.search(value) for value in n.classes))
    if not nodes:
        return None
    node = max(nodes, key=lambda value: len(value.text()))
    return {
        "text": node.text()[:1200],
        "players": _player_observations(node),
        "status": "observed",
    }


def _players_in_segment(segment, players):
    folded = segment.casefold()
    selected = []
    for player in players:
        index = folded.find(player["name"].casefold())
        if index < 0:
            continue
        local_text = segment[max(0, index - 24):index + len(player["name"]) + 48]
        status = STATUS_RE.search(local_text)
        position = POSITION_RE.search(local_text)
        observed = dict(player)
        if status and not observed["status_observation"]:
            observed["status_observation"] = status.group(1).upper()
        if position and not observed["position_observation"]:
            observed["position_observation"] = position.group(1).upper()
        selected.append(observed)
    return selected


def _marked_segment(text, start_pattern, end_pattern=None):
    start = re.search(start_pattern, text, re.I)
    if not start:
        return None
    begin = start.end()
    end = re.search(end_pattern, text[begin:], re.I) if end_pattern else None
    return text[begin:begin + end.start()] if end else text[begin:]


def _team_lineup_observation(box, side):
    side_class = "is-visit" if side == "away" else "is-home"
    candidates = [
        node for node in _find_all(box, lambda n: n.has_class(side_class))
        if not node.has_class("lineup__team")
    ]
    container = max(candidates, key=lambda value: len(value.text())) if candidates else None
    if container is None:
        return {
            "status": "not_exposed_in_page_structure",
            "players": [],
            "goalie": None,
            "power_play_1": None,
            "power_play_2": None,
            "injuries": None,
        }

    text = container.text()
    players = _player_observations(container)
    pp1_text = _marked_segment(text, r"POWER\s+PLAY\s*#?1", r"POWER\s+PLAY\s*#?2|INJURIES")
    pp2_text = _marked_segment(text, r"POWER\s+PLAY\s*#?2", r"INJURIES")
    injury_text = _marked_segment(text, r"INJURIES")
    goalie_text = re.split(r"POWER\s+PLAY\s*#?1", text, flags=re.I)[0] if re.search(r"POWER\s+PLAY\s*#?1", text, re.I) else ""

    def section(segment):
        if segment is None:
            return {"status": "not_identified", "players": [], "text": None}
        return {
            "status": "observed",
            "players": _players_in_segment(segment, players),
            "text": segment.strip()[:1200],
        }

    goalies = _players_in_segment(goalie_text, players)
    goalie = {
        "status": "observed" if goalies else "not_identified",
        "player": goalies[0] if goalies else None,
        "text": goalie_text.strip()[:600] if goalie_text else None,
    }
    return {
        "status": "captured",
        "players": players,
        "goalie": goalie,
        "power_play_1": section(pp1_text),
        "power_play_2": section(pp2_text),
        "injuries": section(injury_text),
        "raw_team_text": text[:3000],
    }


def _market_observation(text):
    normalized = " ".join(text.split())
    line_match = re.search(r"\bLINE\s+([A-Z]{2,3})?\s*([+-]\d{2,4}|[–—-])", normalized, re.I)
    total_match = re.search(r"\bO\s*/\s*U\s*([0-9]+(?:\.[0-9]+)?)\s*(?:Goals?)?", normalized, re.I)
    return {
        "moneyline": {
            "team": line_match.group(1).upper() if line_match and line_match.group(1) else None,
            "american_odds": line_match.group(2) if line_match and line_match.group(2) not in {"-", "–", "—"} else None,
            "raw": line_match.group(0) if line_match else None,
        },
        "total_goals": ({
            "line": float(total_match.group(1)),
            "raw": total_match.group(0),
        } if total_match else None),
    }



def parse_cards(raw):
    parser = DocumentParser()
    parser.feed(raw.decode("utf-8", "replace"))
    boxes = _find_all(parser.root, lambda n: n.has_class("lineup__box"))
    if not boxes:
        raise ValueError("RotoWire page structure changed: no lineup cards")
    cards = []
    for box in boxes:
        teams = _find_all(box, lambda n: n.has_class("lineup__team"))
        visit = [n for n in teams if n.has_class("is-visit")]
        home = [n for n in teams if n.has_class("is-home")]
        if len(visit) != 1 or len(home) != 1:
            continue
        away_code, home_code = _abbr(visit[0]), _abbr(home[0])
        if not away_code or not home_code or away_code == home_code:
            continue
        cards.append({
            "away": away_code,
            "home": home_code,
            "card_text": box.text(),
            "raw_card_sha256": hashlib.sha256(box.text().encode("utf-8")).hexdigest(),
            "away_observation": _team_lineup_observation(box, "away"),
            "home_observation": _team_lineup_observation(box, "home"),
            "market_observation": _market_observation(box.text()),
        })
    if not cards:
        raise ValueError("RotoWire page changed or yielded no identifiable fixtures")
    ids = [(x["away"], x["home"]) for x in cards]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate RotoWire matchup card")
    return cards


def match_fixtures(cards, report, captured_at):
    captured = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    fixtures = {}
    for fixture in report.get("games", []):
        key = (fixture.get("away"), fixture.get("home"))
        if not all(isinstance(x, str) for x in key):
            raise ValueError("Invalid official fixture identity")
        if key in fixtures:
            raise ValueError("Duplicate official fixture")
        fixtures[key] = fixture
    matches, unmatched = [], []
    for card in cards:
        key = (card["away"], card["home"])
        fixture = fixtures.get(key)
        if fixture is None:
            unmatched.append(card)
            continue
        start = datetime.fromisoformat(fixture["start_utc"].replace("Z", "+00:00"))
        if captured >= start:
            continue
        matches.append({
            "game_id": str(fixture["game_id"]),
            "away": card["away"],
            "home": card["home"],
            "start_utc": fixture["start_utc"],
            "source_observation": card["card_text"],
            "source_card_sha256": card["raw_card_sha256"],
            "rotowire_primary_pregame_source": True,
            "away_observation": card["away_observation"],
            "home_observation": card["home_observation"],
            "market_observation": card["market_observation"],
            "confirmed_by_nhl": False,
            "probabilities_modified": False,
        })
    return matches, unmatched


def build(raw, report, captured_at=None):
    metadata = {
        "source_url": URL,
        "retrieved_at_utc": captured_at or datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    cards = parse_cards(raw)
    matches, unmatched = match_fixtures(cards, report, metadata["retrieved_at_utc"])
    return {
        "kind": "nhl_rotowire_pregame_capture_454",
        "captured_at_utc": metadata["retrieved_at_utc"],
        "source": metadata,
        "games": matches,
        "unmatched_cards": unmatched,
        "probabilities_modified": False,
        "official": False,
        "note": "RotoWire observations are preserved for audit; this capture does not alter model percentages.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--raw-out", required=True)
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text())
    raw = b""
    try:
        raw, _ = fetch()
        result = build(raw, report)
    except Exception as error:
        result = {
            "kind": "nhl_rotowire_pregame_capture_454",
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": {
                "source_url": URL,
                "sha256": hashlib.sha256(raw).hexdigest() if raw else None,
            },
            "games": [],
            "unmatched_cards": [],
            "source_error": type(error).__name__ + ": " + str(error)[:240],
            "probabilities_modified": False,
            "official": False,
        }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    Path(args.raw_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.raw_out).write_bytes(raw)
    print(json.dumps({
        "rotowire_cards": len(result["games"]),
        "unmatched_cards": len(result["unmatched_cards"]),
        "source_error": bool(result.get("source_error")),
        "probabilities_modified": False,
    }))


if __name__ == "__main__":
    main()
