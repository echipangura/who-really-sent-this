"""Command-line tool (brief, Week 2 deliverable).

Usage:
    python -m engine analyze sample.eml            # JSON report for one file
    python -m engine analyze a.eml b.eml           # one report per file
    python -m engine summary tests/fixtures        # one line per file, quick overview

Reads only the files you give it. No network access, nothing stored.
"""

from __future__ import annotations

import argparse
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
    print(f"{'file':<46}{'provider':<9}{'spf':<10}{'dkim':<10}{'dmarc':<11}{'aligned':<9}codes")
    for p in files:
        r = analyze(p.read_bytes())
        dkim = ",".join(d["result"] for d in r["auth"]["dkim"]) or "-"
        print(f"{p.name:<46}{r['trust']['provider']:<9}{str(r['auth']['spf']['result']):<10}"
              f"{dkim[:9]:<10}{str(r['auth']['dmarc']['result']):<11}{str(r['identities']['aligned']):<9}"
              f"{' '.join(c for c in r['codes'] if not c.startswith('NORM_'))}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m engine", description="Who Really Sent This? analysis engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="print a JSON report for one or more header files")
    a.add_argument("files", nargs="+", type=Path)
    s = sub.add_parser("summary", help="one line per .eml file in a folder")
    s.add_argument("folder", type=Path)
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
        return _cmd_summary(args.folder)
    except BrokenPipeError:  # output piped into a pager that closed early
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
