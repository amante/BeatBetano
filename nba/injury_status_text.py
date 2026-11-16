"""Small, dependency-free parsing helpers for NBA provider injury statuses."""
import re

STATUS = re.compile(r"\b(Game Time Decision|Out|Doubtful|Questionable|Probable|Available|Injured Reserve)\b", re.I)


def extract_status_candidate(value):
    match = STATUS.search(str(value or ""))
    return match.group(1).title() if match else None
