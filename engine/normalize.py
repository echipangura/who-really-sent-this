"""Normalize a raw email header paste into a clean, parseable header block.

Step 1 of the pipeline (brief, Section 5.2): unfold continuation lines,
handle CRLF, drop the body.

People paste headers in messy ways: with the body attached, with Gmail's
"Show original" summary table on top, with Windows line endings, with a
BOM, or cut off half way. This module turns any of those into one clean
block of "Name: value" lines and reports what it had to fix as warning
codes. It never produces English sentences; the interface turns codes
into words (brief, Section 8.2).

Pure standard library, so it works in the stlite (Pyodide) build.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from email import policy
from email.message import EmailMessage
from email.parser import HeaderParser

# Warning codes (looked up in locales/*.json by the interface).
LEADING_TEXT_REMOVED = "NORM_LEADING_TEXT_REMOVED"
BODY_REMOVED = "NORM_BODY_REMOVED"
MALFORMED_LINE_JOINED = "NORM_MALFORMED_LINE_JOINED"
NO_HEADERS_FOUND = "NORM_NO_HEADERS_FOUND"
POSSIBLY_TRUNCATED = "NORM_POSSIBLY_TRUNCATED"
MISSING_RECEIVED = "NORM_MISSING_RECEIVED"
MISSING_FROM = "NORM_MISSING_FROM"
MISSING_AUTH_RESULTS = "NORM_MISSING_AUTH_RESULTS"
INPUT_TOO_LARGE = "NORM_INPUT_TOO_LARGE"

# Hard limit on what we accept (brief, Week 5: input size limits).
MAX_INPUT_CHARS = 1_000_000

# RFC 5322 field name: printable ASCII except space and colon.
_HEADER_RE = re.compile(r"^([!-9;-~]+):[ \t]?(.*)$")

# Headers that can legitimately start a raw message as it sits in a
# mailbox. Used to skip any junk pasted above the real headers (for
# example Gmail's "Original message" summary table, whose "SPF:" and
# "DKIM:" rows would otherwise look like headers).
_TOP_HEADERS = {
    "delivered-to", "received", "x-received", "return-path", "arc-seal",
    "arc-message-signature", "arc-authentication-results",
    "authentication-results", "received-spf", "dkim-signature",
    "x-google-smtp-source", "x-gm-message-state", "x-ms-exchange-organization-network-message-id",
    "x-ms-exchange-organization-authas", "x-original-to", "x-apparently-to",
    "x-sonic-mf", "x-ymail-osg", "x-mail-from", "mime-version", "from",
    "message-id", "date", "subject", "to", "x-forefront-antispam-report",
    "x-microsoft-antispam", "x-ms-publictraffictype", "x-originating-ip",
}


@dataclass
class NormalizedHeaders:
    """Result of normalization."""

    headers: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Clean header block, one unfolded header per line, LF endings."""
        return "".join(f"{name}: {value}\n" for name, value in self.headers)

    def get_all(self, name: str) -> list[str]:
        """All values for a header name, top to bottom, case-insensitive."""
        lname = name.lower()
        return [v for n, v in self.headers if n.lower() == lname]

    def get(self, name: str) -> str | None:
        values = self.get_all(name)
        return values[0] if values else None

    def to_message(self) -> EmailMessage:
        """Parse the clean block with the standard library (Section 5.2 step 2)."""
        return HeaderParser(policy=policy.default).parsestr(self.text)


def _to_text(raw: str | bytes) -> str:
    if isinstance(raw, bytes):
        # Headers are 7-bit ASCII by standard; tolerate anything else.
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                raw = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    return raw.lstrip("﻿")


def normalize(raw: str | bytes) -> NormalizedHeaders:
    """Turn a raw paste (headers, or a full message) into clean headers."""
    result = NormalizedHeaders()
    text = _to_text(raw)

    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS]
        result.warnings.append(INPUT_TOO_LARGE)

    # CRLF and lone CR to LF; non-breaking spaces that come from copying
    # out of a web page become ordinary spaces.
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    # Trailing newlines at the end of a paste are not a header/body
    # separator; dropping them lets a cut-off paste be detected.
    lines = text.rstrip("\n").split("\n")

    # 1. Find where the real headers start. A paste copied from a mail
    # app's screen can carry stray lines such as "To:" above the real
    # headers, so prefer the first candidate whose block (up to the next
    # blank line) contains a Received header.
    def _is_candidate(i: int) -> bool:
        m = _HEADER_RE.match(lines[i])
        if not m or m.group(1).lower() not in _TOP_HEADERS:
            return False
        # An empty "To:" followed by an unindented line is a label from
        # the mail app's screen (iCloud web), not a header.
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        return bool(m.group(2).strip()) or nxt[:1] in (" ", "\t")

    candidates = [i for i in range(len(lines)) if _is_candidate(i)]
    start = candidates[0] if candidates else None
    for i in candidates:
        block = []
        for line in lines[i:]:
            if not line.strip():
                break
            block.append(line)
        if any(l.lower().startswith("received:") for l in block):
            start = i
            break
    if start is None:
        result.warnings.append(NO_HEADERS_FOUND)
        return result
    if any(l.strip() for l in lines[:start]):
        result.warnings.append(LEADING_TEXT_REMOVED)

    # 2. Collect header lines until the first blank line (start of body).
    headers: list[list[str]] = []
    body_seen = False
    block = lines[start:]
    end = next((k for k, l in enumerate(block) if not l.strip()), len(block))
    # Index of the last real header line in the block. Plain text after
    # it (no blank line in between) is body text that a web mail app
    # copied along with the headers, for example iCloud's message preview.
    last_header = max(k for k in range(end) if _HEADER_RE.match(block[k]))
    for offset, line in enumerate(block):
        if not line.strip():
            body_seen = True
            if any(l.strip() for l in block[offset + 1:]):
                result.warnings.append(BODY_REMOVED)
            break
        if offset > last_header and line[:1] not in (" ", "\t"):
            body_seen = True
            result.warnings.append(BODY_REMOVED)
            break
        if line[:1] in (" ", "\t"):
            # Continuation of the previous header: unfold.
            if headers:
                headers[-1][1] += " " + line.strip()
            continue
        m = _HEADER_RE.match(line)
        if m:
            headers.append([m.group(1), m.group(2).strip()])
        elif headers:
            # A line that is neither a header nor indented, usually a
            # copy-paste that lost the indentation. Keep it with the
            # header above rather than losing evidence.
            headers[-1][1] += " " + line.strip()
            if MALFORMED_LINE_JOINED not in result.warnings:
                result.warnings.append(MALFORMED_LINE_JOINED)

    # Collapse runs of whitespace inside values (left over from unfolding).
    result.headers = [(n, re.sub(r"[ \t]+", " ", v).strip()) for n, v in headers]

    # 3. Sanity checks that later stages rely on.
    names = {n.lower() for n, _ in result.headers}
    if "received" not in names:
        result.warnings.append(MISSING_RECEIVED)
    if "from" not in names:
        result.warnings.append(MISSING_FROM)
    if not names & {"authentication-results", "arc-authentication-results"}:
        result.warnings.append(MISSING_AUTH_RESULTS)
    # A paste that ends without a blank line and is missing From usually
    # means the user stopped copying too early.
    if not body_seen and "from" not in names:
        result.warnings.append(POSSIBLY_TRUNCATED)

    return result
