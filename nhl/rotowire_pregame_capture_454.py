"""Capture and validate dated RotoWire NHL pregame cards.

The public page is treated as an observation source, not as official NHL data.
This first integration preserves the source snapshot and maps visible game cards
to official fixtures. It does not modify model probabilities.
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

    def text(self):
        return " ".join(" ".join(self.parts + [child.text() for child in self.children]).split())

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
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs, self.stack[-1]))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        if self.stack:
            self.stack[-1].parts.append(data)


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
