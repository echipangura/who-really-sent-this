"""Find the trust boundary: the authentication stamp the user's own
mail provider wrote (brief, Section 5.1).

Every server a message passes through can add headers, and anyone can
type a fake "Authentication-Results: mx.google.com; dmarc=pass" into a
message before sending it. The only stamp we can believe is the one the
receiving provider added on arrival. Providers add their headers on top
of the ones already there, so the provider's real stamp is the FIRST
(topmost) one carrying its own server name. Anything with the same name
further down was written earlier, by someone else, and is ignored.

How each provider signs its stamp (the "authserv-id", the first item on
the line):
  Gmail    mx.google.com
  Outlook  mx.microsoft.com 1, or no name at all in older Microsoft mail
  Yahoo    *.yahoo.com (mta.yahoo.com)
  iCloud   several lines: dmarc.icloud.com, dkim-verifier.icloud.com,
           spf.icloud.com, arc.icloud.com, bimi.icloud.com

The engine emits codes; the interface turns them into words.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from engine.normalize import NormalizedHeaders

GMAIL, OUTLOOK, YAHOO, ICLOUD, GENERIC = "gmail", "outlook", "yahoo", "icloud", "generic"

# Codes
TRUST_PROVIDER_STAMP = "TRUST_PROVIDER_STAMP"    # found the provider's own stamp
TRUST_GENERIC_STAMP = "TRUST_GENERIC_STAMP"      # unknown provider: using topmost stamp
TRUST_NO_STAMP = "TRUST_NO_STAMP"                # no Authentication-Results at all


@dataclass
class TrustInfo:
    provider: str
    status: str
    # Trusted Authentication-Results values, top to bottom. One for most
    # providers, several for iCloud (one per check).
    stamps: list[str] = field(default_factory=list)
    # Position of the topmost trusted stamp in the header list. Headers
    # above it were added by the provider; headers below are "claimed by
    # the sender" and are shown as such in the hop map.
    boundary_index: int | None = None


def authserv_id(value: str) -> str:
    """The server name at the start of an Authentication-Results value,
    or "" when the value starts straight with a result (spf=..., as in
    older Microsoft mail)."""
    first = value.split(";", 1)[0].strip()
    if "=" in first:
        return ""
    return first.split()[0].lower() if first else ""


def _provider_of_authserv(sid: str) -> str | None:
    if sid == "mx.google.com":
        return GMAIL
    if sid == "mx.microsoft.com" or sid.endswith(".outlook.com") or sid.endswith(".office365.com"):
        return OUTLOOK
    if sid.endswith(".yahoo.com") or sid == "yahoo.com":
        return YAHOO
    if sid.endswith(".icloud.com") or sid == "icloud.com":
        return ICLOUD
    return None


_BY_HOST = re.compile(r"\bby\s+([^\s;()]+)", re.I)


def _received_mentions_microsoft(headers: NormalizedHeaders) -> bool:
    for value in headers.get_all("Received")[:4]:
        m = _BY_HOST.search(value)
        if m and re.search(r"(outlook\.com|office365\.com|protection\.outlook\.com)$", m.group(1).lower()):
            return True
    return False


def find_trust_boundary(headers: NormalizedHeaders) -> TrustInfo:
    """Identify the provider and return its trusted stamp(s)."""
    ar = [(i, v) for i, (n, v) in enumerate(headers.headers) if n.lower() == "authentication-results"]
    if not ar:
        return TrustInfo(provider=GENERIC, status=TRUST_NO_STAMP)

    top_index, top_value = ar[0]
    sid = authserv_id(top_value)
    provider = _provider_of_authserv(sid) if sid else None
    if provider is None and not sid and _received_mentions_microsoft(headers):
        provider = OUTLOOK

    if provider is None:
        return TrustInfo(provider=GENERIC, status=TRUST_GENERIC_STAMP,
                         stamps=[top_value], boundary_index=top_index)

    if provider == ICLOUD:
        # Take the topmost line for each iCloud checker; a later line with
        # the same name could have been planted by the sender.
        seen, stamps, first = set(), [], None
        for i, v in ar:
            s = authserv_id(v)
            if _provider_of_authserv(s) == ICLOUD and s not in seen:
                seen.add(s)
                stamps.append(v)
                first = i if first is None else first
        return TrustInfo(provider=ICLOUD, status=TRUST_PROVIDER_STAMP,
                         stamps=stamps, boundary_index=first)

    # Gmail, Outlook, Yahoo: one stamp, the topmost carrying the provider's
    # name (or, for nameless Microsoft stamps, the topmost stamp).
    for i, v in ar:
        s = authserv_id(v)
        if (provider == OUTLOOK and not s) or _provider_of_authserv(s) == provider:
            return TrustInfo(provider=provider, status=TRUST_PROVIDER_STAMP,
                             stamps=[v], boundary_index=i)
    return TrustInfo(provider=GENERIC, status=TRUST_GENERIC_STAMP,
                     stamps=[top_value], boundary_index=top_index)
