"""Clean a folder of raw header samples into anonymized test fixtures.

Usage (from the repo root):

    python scripts/clean_corpus.py RAW_FOLDER \
        --redact you@gmail.com --redact you@outlook.com --redact "Your Name"

For every .eml or .txt file in RAW_FOLDER this script:
  1. normalizes the headers (engine/normalize.py): unfolds lines, fixes
     line endings, drops the body and any junk pasted above the headers;
  2. replaces each --redact value with a placeholder. For an address
     only the username changes (you@gmail.com becomes recipient1@gmail.com)
     so SPF, DKIM and DMARC alignment still match the real message
     (brief, Section 8.2: keep the domains, Received hostnames and IPs,
     since those are the evidence);
  3. writes the clean headers to tests/fixtures/<same name>.eml;
  4. writes corpus_report.csv with one row per sample so you can see what
     was fixed and what still needs a look;
  5. adds any new files to tests/fixtures/manifest.csv with the provider
     filled in and the verdict left blank for you to label.

The raw folder is never modified. Keep it out of the repository.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import quopri
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.normalize import normalize  # noqa: E402

FIXTURES = Path("tests/fixtures")
MANIFEST = FIXTURES / "manifest.csv"
MANIFEST_COLUMNS = ["file", "provider", "expected_verdict", "expected_flags", "notes"]
REPORT_COLUMNS = [
    "file", "source", "provider", "headers", "received_hops",
    "auth_results", "arc", "from", "warnings", "privacy_check",
]

_ENCODED_WORD_RE = re.compile(r"=\?([\w-]+)\?([BbQq])\?([^?\s]*)\?=")
_ADDR_RE =re.compile(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+")
_RECIPIENT_HEADERS = ("to", "cc", "delivered-to", "x-original-to", "x-apparently-to")


def _provider_of(host: str) -> str | None:
    host = host.lower()
    if "google.com" in host:
        return "gmail"
    if "outlook.com" in host or "office365" in host or "microsoft" in host:
        return "outlook"
    if "yahoo" in host or "aol" in host:
        return "yahoo"
    if "icloud" in host or "me.com" in host or "apple" in host:
        return "icloud"
    return None


def detect_provider(auth_results: list[str], received: list[str]) -> str:
    """Guess the receiving provider from the topmost authserv-id, or,
    since Microsoft often omits the authserv-id, from the 'by' host of
    the topmost Received line."""
    for value in auth_results:
        found = _provider_of(value.split(";", 1)[0])
        if found:
            return found
    for value in received[:1]:
        m = re.search(r"\bby\s+(\S+)", value)
        if m and (found := _provider_of(m.group(1))):
            return found
    return "unknown"


def build_redactor(values: list[str]):
    """Return a function that swaps each redacted value for a placeholder.

    For an address like you@gmail.com it also catches the forms that
    bulk senders and spammers use: the bounce (VERP) encoding
    "you=gmail.com@..." and the bare username "you" on its own.
    Plain names are matched as whole words.
    """
    full, locals_, names = [], {}, []
    addr_n = name_n = 0
    for value in values:
        if "@" in value:
            addr_n += 1
            local, domain = value.rsplit("@", 1)
            full.append((value, f"recipient{addr_n}@{domain}"))
            full.append((f"{local}={domain}", f"recipient{addr_n}={domain}"))
            locals_.setdefault(local.lower(), f"recipient{addr_n}")
        else:
            name_n += 1
            names.append((value, f"Recipient {name_n}"))

    rules = [(re.compile(re.escape(v), re.IGNORECASE), r) for v, r in full]
    # Longest first, so "user1981" is replaced before "user1".
    for local in sorted(locals_, key=len, reverse=True):
        rules.append((re.compile(rf"(?<![\w.+]){re.escape(local)}(?![\w])", re.IGNORECASE), locals_[local]))
    for v, r in sorted(names, key=lambda x: len(x[0]), reverse=True):
        rules.append((re.compile(rf"\b{re.escape(v)}\b", re.IGNORECASE), r))

    def plain(text: str) -> str:
        for pattern, repl in rules:
            text = pattern.sub(repl, text)
        return text

    def encoded_word(m: re.Match) -> str:
        # RFC 2047 encoded words (=?utf-8?B?...?=) can hide a name or an
        # address from a plain search. Decode, redact, and re-encode in
        # the same charset and encoding so the header keeps its shape.
        charset, enc, data = m.group(1), m.group(2).upper(), m.group(3)
        try:
            if enc == "B":
                raw = base64.b64decode(data + "=" * (-len(data) % 4))
            else:
                raw = quopri.decodestring(data.replace("_", " ").encode(), header=True)
            decoded = raw.decode(charset, errors="strict")
        except (ValueError, LookupError, binascii.Error):
            return m.group(0)
        cleaned = plain(decoded)
        if cleaned == decoded:
            return m.group(0)
        if enc == "B":
            body = base64.b64encode(cleaned.encode(charset)).decode()
        else:
            body = quopri.encodestring(cleaned.encode(charset), header=True).decode()
        return f"=?{charset}?{m.group(2)}?{body}?="

    def redact(text: str) -> str:
        return plain(_ENCODED_WORD_RE.sub(encoded_word, text))

    return redact


def privacy_leftovers(headers: list[tuple[str, str]]) -> str:
    """Recipient addresses whose username was not replaced: review these."""
    left = set()
    for name, value in headers:
        if name.lower() in _RECIPIENT_HEADERS:
            for addr in _ADDR_RE.findall(value):
                if not re.match(r"recipient\d+@", addr.lower()):
                    left.add(addr)
    return " ".join(sorted(left))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw_folder", type=Path)
    ap.add_argument("--redact", action="append", default=[], help="address or name to anonymize (repeatable)")
    ap.add_argument("--out", type=Path, default=FIXTURES)
    ap.add_argument("--report", type=Path, default=Path("corpus_report.csv"))
    args = ap.parse_args()

    files = sorted(p for p in args.raw_folder.iterdir() if p.suffix.lower() in (".eml", ".txt"))
    if not files:
        print(f"No .eml or .txt files found in {args.raw_folder}")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    redact = build_redactor(args.redact)

    # Normalize first, then redact, so a name split across folded lines
    # is caught once the lines are joined.
    rows = []
    for src in files:
        norm = normalize(src.read_bytes())
        norm.headers = [(n, redact(v)) for n, v in norm.headers]
        out_name = re.sub(r"[^\w.-]+", "_", src.stem) + ".eml"
        (args.out / out_name).write_text(norm.text, encoding="utf-8")

        auth = norm.get_all("Authentication-Results") or norm.get_all("ARC-Authentication-Results")
        rows.append({
            "file": out_name,
            "source": src.name,
            "provider": detect_provider(auth, norm.get_all("Received")),
            "headers": len(norm.headers),
            "received_hops": len(norm.get_all("Received")),
            "auth_results": "yes" if norm.get_all("Authentication-Results") else "no",
            "arc": "yes" if norm.get_all("ARC-Seal") else "no",
            "from": norm.get("From") or "",
            "warnings": " ".join(norm.warnings),
            "privacy_check": privacy_leftovers(norm.headers),
        })

    with args.report.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=REPORT_COLUMNS)
        w.writeheader()
        w.writerows(rows)

    # Add new fixtures to the manifest without touching existing labels.
    existing = []
    if MANIFEST.exists():
        with MANIFEST.open(newline="", encoding="utf-8") as fh:
            existing = [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(fh)]
    known = {r["file"] for r in existing}
    added = [
        {"file": r["file"], "provider": r["provider"], "expected_verdict": "", "expected_flags": "", "notes": ""}
        for r in rows if r["file"] not in known
    ]
    with MANIFEST.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        w.writeheader()
        w.writerows(existing + added)

    # Removing a body or screen text is routine; anything else needs a look.
    routine = {"NORM_BODY_REMOVED", "NORM_LEADING_TEXT_REMOVED"}
    flagged = [r for r in rows if set(r["warnings"].split()) - routine or r["privacy_check"]]
    print(f"Cleaned {len(rows)} samples into {args.out}/")
    print(f"Report: {args.report}  |  Manifest: {len(added)} new rows added")
    print(f"{len(flagged)} samples need a look (see warnings / privacy_check columns)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
