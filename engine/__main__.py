"""Command-line tool (brief, Week 2 deliverable).

Usage:
    python -m engine analyze sample.eml            # JSON report for one file
    python -m engine analyze a.eml b.eml           # one report per file
    python -m engine summary tests/fixtures        # one line per file, quick overview
    python -m engine evaluate tests/fixtures       # verdicts vs manifest.csv (Gate 1)

Reads only the files you give it. No network access, nothing stored.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from engine.analyze import analyze


def _cmd_analyze(paths: list[Path]) -> int:
    reports = []
    for p in paths:
        report = analyze(p.read_bytes())
        report["file"] = p.name
        reports.append(report)
    out = reports[0] if len(reports) == 1 else reports
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _cmd_summary(folder: Path) -> int:
    files = sorted(folder.glob("*.eml"))
    if not files:
        print(f"No .eml files in {folder}")
        return 1
    print(f"{'file':<44}{'verdict':<13}{'spf':<10}{'dmarc':<11}{'aligned':<9}reasons")
    for p in files:
        r = analyze(p.read_bytes())
        reasons = " ".join(x.removeprefix("RULE_") for x in r["verdict"]["reasons"]) or "-"
        print(f"{p.name[:43]:<44}{r['verdict']['tier']:<13}{str(r['auth']['spf']['result']):<10}"
              f"{str(r['auth']['dmarc']['result']):<11}{str(r['identities']['aligned']):<9}{reasons}")
    return 0


def evaluate(folder: Path) -> dict:
    """Compare engine verdicts with the hand labels in manifest.csv."""
    with (folder / "manifest.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    tiers = ["CHECKS_OUT", "BE_CAREFUL", "LIKELY_SCAM"]
    matrix = {e: {g: 0 for g in tiers} for e in tiers}
    misses, legit_red = [], []
    for row in rows:
        got = analyze((folder / row["file"]).read_bytes())["verdict"]["tier"]
        matrix[row["expected_verdict"]][got] += 1
        if got != row["expected_verdict"]:
            misses.append((row["file"], row["expected_verdict"], got))
        if row["file"].startswith("legit") and got == "LIKELY_SCAM":
            legit_red.append(row["file"])
    total = len(rows)
    return {"total": total, "agree": total - len(misses), "matrix": matrix,
            "misses": misses, "legit_red": legit_red}


def _cmd_evaluate(folder: Path) -> int:
    r = evaluate(folder)
    pct = 100 * r["agree"] / r["total"] if r["total"] else 0
    tiers = list(r["matrix"])
    print(f"Verdict agreement with manifest: {r['agree']}/{r['total']} = {pct:.1f}%")
    print(f"LIKELY_SCAM on legitimate samples: {len(r['legit_red'])}")
    print()
    print(f"{'label → engine':<20}" + "".join(f"{t:>14}" for t in tiers))
    for e in tiers:
        print(f"{e:<20}" + "".join(f"{r['matrix'][e][g]:>14}" for g in tiers))
    for f, e, g in r["misses"]:
        print(f"  differs: {f}  labelled {e}, engine says {g}")
    gate = pct >= 90 and not r["legit_red"]
    print()
    print("Gate 1:", "PASS" if gate else "NOT YET", "(needs >= 90% agreement and 0 red on legit)")
    return 0 if gate else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m engine", description="Who Really Sent This? analysis engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="print a JSON report for one or more header files")
    a.add_argument("files", nargs="+", type=Path)
    s = sub.add_parser("summary", help="one line per .eml file in a folder")
    s.add_argument("folder", type=Path)
    e = sub.add_parser("evaluate", help="compare verdicts with manifest.csv (Gate 1)")
    e.add_argument("folder", type=Path)
    args = ap.parse_args(argv)

    # Windows consoles default to a legacy code page; force UTF-8 so
    # display names with accents or emoji print correctly.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    try:
        if args.cmd == "analyze":
            return _cmd_analyze(args.files)
        if args.cmd == "evaluate":
            return _cmd_evaluate(args.folder)
        return _cmd_summary(args.folder)
    except BrokenPipeError:  # output piped into a pager that closed early
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
