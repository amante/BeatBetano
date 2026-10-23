# NFL.com 3.1 — structured extraction from authenticated captures

An optional parser reads an HTML archive written by nflcom_capture.py, checks its SHA-256 digest, and extracts only explicitly labelled Player / Position / Game Status table rows. Dynamic JavaScript pages may produce no rows; the parser fails closed instead of guessing.

Parsing does NOT imply player GSIS identity, game/team linkage, known starter status, or that a page was available pre-kickoff. Extracted rows retain their actual retrieval timestamp. A future audited join must obtain team/game mapping and verify the kickoff threshold independently before inclusion in backtests.

This is not a scraper that bypasses site controls and does not create historical point-in-time information retroactively.
