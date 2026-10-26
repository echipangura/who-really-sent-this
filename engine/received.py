"""The journey: turn the Received chain into a hop map
(brief, Section 5.2 step 7 and the "Hop anomalies" check in 5.3).

Every mail server that handles a message adds one Received line ON TOP
of the ones already there, so reading the chain from the bottom up gives
the route in the order it happened, like a traceroute for email:

  Received: from A (ptr [ip]) by B with ESMTPS id ...; <date>

  from     the name the sending server gave for itself (its HELO; anyone
           can type anything here)
  ptr      the name the receiving server found for that IP address (more
           trustworthy than the HELO, but only if the receiver is honest)
  ip       the address the connection actually came from
  by       the receiving server
  with     the protocol (SMTP, ESMTPS = encrypted, HTTP = webmail)

Trust works the same way as for Authentication-Results (trust.py): only
the lines the user's own provider wrote can be believed. The "entry hop"
is the line where the provider accepted the message from the outside
world. That hop and everything above it were written by the provider;
every hop below it is "claimed by the sender" and may be invented.

The entry hop is found, in order of preference, by:
  1. the sender IP the provider names in its trusted stamp
     ("designates 146.143.8.26 as permitted sender", "sender IP is ..."),
  2. walking down from the top while the receiving server belongs to the
     provider, and stopping at the first hop whose sender does not,
  3. the topmost Received line.

Codes only; the interface turns them into words.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from engine.normalize import NormalizedHeaders
from engine.trust import GMAIL, ICLOUD, OUTLOOK, YAHOO, TrustInfo

# Codes
HOP_NONE = "HOP_NONE"                          # no Received lines at all
HOP_MALFORMED = "HOP_MALFORMED"                # a line with no "by" or no readable date
HOP_FORGED_PROVIDER = "HOP_FORGED_PROVIDER"    # a sender-claimed hop says it was received by the provider
HOP_TIME_REVERSED = "HOP_TIME_REVERSED"        # a later hop is stamped well before an earlier one
HOP_LONG_DELAY = "HOP_LONG_DELAY"              # the message sat somewhere for over a day
HOP_ENTRY_UNRELATED = "HOP_ENTRY_UNRELATED"    # first outside server has nothing to do with the From
                                               # domain, and the domain did not vouch for it (not aligned)

# Allowances. Server clocks drift and queues retry, so small reversals and
# delays are normal; these thresholds only catch the implausible.
CLOCK_SKEW_SECONDS = 15 * 60
LONG_DELAY_SECONDS = 24 * 60 * 60

# Registrable domains of each provider's own mail servers.
_PROVIDER_DOMAINS = {
    GMAIL: {"google.com"},
    OUTLOOK: {"outlook.com", "office365.com"},
    YAHOO: {"yahoo.com", "yahoo.net", "yahoodns.net", "aol.com"},
    ICLOUD: {"icloud.com", "me.com"},
}
# The provider's public receiving hostnames. A "by" with one of these on a
# sender-claimed hop is a forgery: the provider did not write that line.
# Only providers whose receiving name never appears on the sending side:
# a sender on Microsoft 365 passes through *.mail.protection.outlook.com
# too, so Outlook is left out.
_PROVIDER_MX = {
    GMAIL: re.compile(r"^mx\.google\.com$"),
    ICLOUD: re.compile(r"^mx\d*\.mail\.icloud\.com$"),
}

_STAMP_IP = re.compile(
    r"(?:designates|sender IP is|client-ip=|smtp\.remote-ip=)\s*\(?\[?([0-9a-fA-F:.]{7,})", re.I)
_IP_IN_BRACKETS = re.compile(r"\[(?:IPv6:)?([0-9a-fA-F:.]+)\]")
# Dates for lines with no ";" before the date (SendGrid internal hops).
_RFC_DATE = re.compile(r"(?:[A-Z][a-z]{2},\s*)?\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?\s+[+-]\d{4}")
_ISO_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.\d+)?\s*([+-]\d{4}|Z|UTC)?")
_FRACTION = re.compile(r"(\d{1,2}:\d{2}:\d{2})\.\d+")
_HOSTNAME = re.compile(r"^[A-Za-z0-9_](?:[A-Za-z0-9_-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9_-]+)*\.?$")


@dataclass
class Hop:
    number: int                     # 1 = first server, counting toward the inbox
    from_host: str | None = None    # name the sender gave (HELO)
    from_ptr: str | None = None     # name the receiver recorded for the IP
    from_ip: str | None = None
    by_host: str | None = None
    protocol: str | None = None
    timestamp: str | None = None    # ISO 8601, UTC
    delay_seconds: int | None = None  # since the previous hop
    trusted: bool = False           # written by the user's provider
    entry: bool = False             # where the provider accepted it from outside
    raw: str = ""


@dataclass
class HopMap:
    hops: list[Hop] = field(default_factory=list)   # oldest first
    entry_number: int | None = None
    total_seconds: int | None = None
    codes: list[str] = field(default_factory=list)

    @property
    def entry(self) -> Hop | None:
        return next((h for h in self.hops if h.entry), None)

    @property
    def first_claimed(self) -> Hop | None:
        """The server the message says it started from (may be invented)."""
        return self.hops[0] if self.hops else None


def _valid_ip(s: str | None) -> str | None:
    if not s:
        return None
    try:
        return str(ipaddress.ip_address(s.strip().rstrip(".")))
    except ValueError:
        return None


def _clean_host(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip().strip("[]").rstrip(".").lower()
    return s or None


def _split_top(text: str) -> list[str]:
    """Split on whitespace outside parentheses, keeping (comments) as one token."""
    tokens, buf, depth = [], [], 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(depth - 1, 0)
        if ch.isspace() and depth == 0:
            if buf:
                tokens.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def parse_received(value: str) -> Hop:
    """Parse one Received value. Never raises; missing parts stay None."""
    hop = Hop(number=0, raw=value)
    body, _, date_part = value.rpartition(";")
    if not body:                       # no ";": look for a date anywhere
        body, date_part = value, ""
    dt = _parse_date(date_part) or _parse_date(value, search=True)
    if dt:
        hop.timestamp = dt.isoformat()

    tokens = _split_top(body)
    i = 0
    while i < len(tokens):
        word = tokens[i].lower()
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if word == "from" and nxt and hop.by_host is None:
            hop.from_host = _clean_host(nxt) if not nxt.startswith("(") else None
            i += 2
            # The comment(s) right after the HELO: PTR name, [IP], EHLO name.
            while i < len(tokens) and tokens[i].startswith("("):
                _read_from_comment(hop, tokens[i][1:-1] if tokens[i].endswith(")") else tokens[i][1:])
                i += 1
            continue
        if word == "by" and nxt and hop.by_host is None:
            hop.by_host = _clean_host(nxt)
            i += 2
            continue
        if word == "with" and nxt and hop.protocol is None:
            hop.protocol = nxt.upper()
            i += 2
            continue
        i += 1

    # "from 1.2.3.4" / "from [1.2.3.4]": the HELO is an address.
    if hop.from_host:
        ip = _valid_ip(hop.from_host)
        if ip:
            hop.from_ip = hop.from_ip or ip
            hop.from_host = None
    return hop


def _parse_date(text: str, search: bool = False) -> datetime | None:
    text = text.strip()
    if not text:
        return None
    candidates = [text] if not search else []
    m = _RFC_DATE.search(text)
    if m:
        candidates.append(m.group(0))
    for c in candidates:
        try:
            dt = parsedate_to_datetime(_FRACTION.sub(r"\1", c))
        except (TypeError, ValueError, IndexError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    m = _ISO_DATE.search(text)
    if m:
        try:
            dt = datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}")
        except ValueError:
            return None
        tz = m.group(3)
        if tz and tz[0] in "+-":
            dt = datetime.strptime(f"{m.group(1)}T{m.group(2)}{tz}", "%Y-%m-%dT%H:%M:%S%z")
        else:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def _read_from_comment(hop: Hop, comment: str) -> None:
    m = _IP_IN_BRACKETS.search(comment)
    if m and _valid_ip(m.group(1)):
        hop.from_ip = hop.from_ip or _valid_ip(m.group(1))
    words = [w.strip("[](),") for w in comment.replace("=", " ").split()]
    for j, w in enumerate(words):
        lw = w.lower()
        if lw in ("ehlo", "helo") and j + 1 < len(words):
            helo = _clean_host(words[j + 1])
            if helo and not _valid_ip(helo):
                # Yahoo style "from 1.2.3.4 (EHLO mail.x.com)": the name
                # after EHLO is the HELO; the leading token was the IP.
                if hop.from_host is None or _valid_ip(hop.from_host):
                    if hop.from_host:
                        hop.from_ip = hop.from_ip or _valid_ip(hop.from_host)
                    hop.from_host = helo
            continue
        if not hop.from_ip and _valid_ip(w):
            hop.from_ip = _valid_ip(w)
            continue
        if (hop.from_ptr is None and "." in w and _HOSTNAME.match(w) and not _valid_ip(w)
                and (j == 0 or words[j - 1].lower() not in ("ehlo", "helo"))):
            hop.from_ptr = _clean_host(w)


def _registrable(host: str | None) -> str | None:
    from engine.identities import registrable  # local import: avoid a cycle
    return registrable(host)


def _is_internal(host: str | None) -> bool:
    """Internal names: no dots (iCloud pods), or private/IPv6-literal addresses."""
    if not host:
        return True
    ip = _valid_ip(host)
    if ip:
        a = ipaddress.ip_address(ip)
        return a.is_private or a.is_loopback or a.version == 6
    return "." not in host


def _is_provider(host: str | None, provider: str) -> bool:
    if _is_internal(host):
        return True
    return _registrable(host) in _PROVIDER_DOMAINS.get(provider, set())


def _stamp_ips(trust: TrustInfo) -> set[str]:
    ips = set()
    for s in trust.stamps:
        for m in _STAMP_IP.finditer(s):
            ip = _valid_ip(m.group(1))
            if ip:
                ips.add(ip)
    return ips


def build_hop_map(headers: NormalizedHeaders, trust: TrustInfo, ids=None) -> HopMap:
    """Hop map, oldest hop first. Pass the Identities (identities.py) to
    also check the entry server against the From domain."""
    values = headers.get_all("Received")            # top (newest) first
    hm = HopMap()
    if not values:
        hm.codes.append(HOP_NONE)
        return hm

    parsed = [parse_received(v) for v in values]

    # Find the entry hop (index into the top-first list).
    entry = None
    ips = _stamp_ips(trust)
    if ips:
        entry = next((i for i, h in enumerate(parsed) if h.from_ip in ips), None)
    if entry is None and trust.provider in _PROVIDER_DOMAINS:
        for i, h in enumerate(parsed):
            if not _is_provider(h.by_host, trust.provider):
                break
            sender = h.from_ptr or h.from_host
            if h.from_host is None and h.from_ip is None and h.from_ptr is None:
                continue                              # "by x with SMTP id": local hand-off
            if not _is_provider(sender, trust.provider) or (
                    sender is None and h.from_ip and not _is_internal(h.from_ip)):
                entry = i
                break
    if entry is None:
        entry = 0

    # Chronological order: bottom of the header is hop 1.
    n = len(parsed)
    hops = list(reversed(parsed))
    for k, h in enumerate(hops):
        h.number = k + 1
        top_index = n - 1 - k
        h.trusted = top_index <= entry
        h.entry = top_index == entry
    hm.hops = hops
    hm.entry_number = n - entry

    # Times between hops.
    prev = None
    first_t = last_t = None
    for h in hops:
        if h.by_host is None or h.timestamp is None:
            if HOP_MALFORMED not in hm.codes:
                hm.codes.append(HOP_MALFORMED)
        t = datetime.fromisoformat(h.timestamp) if h.timestamp else None
        if t and prev:
            h.delay_seconds = int((t - prev).total_seconds())
            if h.delay_seconds < -CLOCK_SKEW_SECONDS and HOP_TIME_REVERSED not in hm.codes:
                hm.codes.append(HOP_TIME_REVERSED)
            if h.delay_seconds > LONG_DELAY_SECONDS and HOP_LONG_DELAY not in hm.codes:
                hm.codes.append(HOP_LONG_DELAY)
        if t:
            prev = t
            first_t = first_t or t
            last_t = t
    if first_t and last_t:
        hm.total_seconds = int((last_t - first_t).total_seconds())

    # A hop the sender wrote that claims the provider received it.
    mx = _PROVIDER_MX.get(trust.provider)
    if mx and any(not h.trusted and h.by_host and mx.search(h.by_host) for h in hops):
        hm.codes.append(HOP_FORGED_PROVIDER)

    # The first outside server, as the provider saw it. Mail services
    # (Amazon SES, SendGrid) legitimately send for other domains, so this
    # only counts when the From domain did not vouch for the message.
    e = hm.entry
    if ids is not None and e is not None and ids.from_domain and not ids.aligned:
        sender = e.from_ptr or e.from_host
        sender_org = _registrable(sender)
        # With no PTR recorded, the only name is the HELO, which the sender
        # typed. If SPF did not pass, nothing backs that name up ("EHLO
        # online.de" from an IP online.de never authorised), so it proves
        # no connection to the From domain.
        if not e.from_ptr and not ids.spf_pass:
            sender_org = None
        # Domains that actually passed a check; a domain named in a failed
        # or "none" SPF result vouched for nothing.
        vouched = {ids.from_org, *ids.dkim_pass_orgs}
        if ids.spf_pass:
            vouched.add(ids.spf_org)
        vouched.discard(None)
        if (sender or e.from_ip) and sender_org not in vouched:
            hm.codes.append(HOP_ENTRY_UNRELATED)
    return hm
