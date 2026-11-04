"""Explicit provider abbreviation equivalences; never fuzzy-match franchises."""
ALIASES={'NYK':'NY','SAS':'SA','NOP':'NO','UTA':'UTAH','WAS':'WSH','GSW':'GS'}

def canonical(value):
    code=str(value or '').strip().upper()
    return ALIASES.get(code,code)

def same_team(a,b):
    return bool(canonical(a)) and canonical(a)==canonical(b)
