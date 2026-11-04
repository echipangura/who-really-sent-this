"""Check several emails at once (brief, Gate 3: batch mode).

A school front office or library desk can save a week of "is this real?"
emails as files and check them together. Each file goes through the same
analyze() as a single paste; results are sorted so the riskiest come first.

Nothing is stored: files arrive as bytes in memory, the rows are returned,
and the CSV summary is built as a string for the reader to download.
Holds no user-facing English: column names and words come from locales/.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Callable, Iterable

from engine.analyze import analyze

MAX_FILES = 50
MAX_FILE_BYTES = 2_000_000          # a whole .eml with attachments can be large; headers are not
RISK_ORDER = {"LIKELY_SCAM": 0, "BE_CAREFUL": 1, "CHECKS_OUT": 2}


@dataclass(frozen=True)
class BatchRow:
    name: str
    tier: str | None                 # None when the file could not be read
    reason: str | None               # first RULE_ code, if any
    claimed: str                     # institution name the email pretends to be, if any
    from_display: str
    from_address: str
    report: dict | None


def check_many(files: Iterable[tuple[str, bytes]]) -> list[BatchRow]:
    """Analyze up to MAX_FILES (name, bytes) pairs; riskiest first, then by name."""
    rows = []
    for name, data in list(files)[:MAX_FILES]:
        if len(data) > MAX_FILE_BYTES:
            data = data[:MAX_FILE_BYTES]   # headers come first; the body is not needed
        try:
            report = analyze(data)
        except Exception:                  # a broken file must not stop the others
            rows.append(BatchRow(name, None, None, "", "", "", None))
            continue
        v, ids = report["verdict"], report["identities"]
        claimed = ((report.get("impersonation") or {}).get("claimed") or {}).get("name", "")
        rows.append(BatchRow(name, v["tier"], (v["reasons"] or [None])[0], claimed,
                             ids.get("from_display") or "", ids.get("from_address") or "", report))
    return sorted(rows, key=lambda r: (RISK_ORDER.get(r.tier, -1), r.name.lower()))


def counts(rows: list[BatchRow]) -> dict[str, int]:
    out = {tier: 0 for tier in RISK_ORDER}
    out["UNREADABLE"] = 0
    for r in rows:
        out[r.tier or "UNREADABLE"] += 1
    return out


def to_csv(rows: list[BatchRow], t: Callable[..., str]) -> str:
    """A CSV summary in the reader's language. t(key, **values) gives the words."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([t("batch.col_file"), t("batch.col_result"), t("batch.col_reason"),
                t("batch.col_name"), t("batch.col_address")])
    for r in rows:
        result = t(f"verdict.{r.tier}.title") if r.tier else t("batch.unreadable")
        reason = t(f"rule.{r.reason}", name=r.claimed) if r.reason else ""
        w.writerow([_safe(x) for x in (r.name, result, reason, r.from_display, r.from_address)])
    return buf.getvalue()


def _safe(value: str) -> str:
    """Stop a spreadsheet treating a scammer's display name as a formula."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value
