"""Who the email says it is from, and who actually vouched for it
(brief, Section 5.2 steps 5 and 6).

An email carries several identities that can all be different:

  From         the address the reader sees ("Chase <alerts@chase.com>")
  Reply-To     where a reply would actually go
  Return-Path  the envelope sender, where bounces go (SPF checks this one)
  DKIM d=      the domain that signed the message
  SPF domain   the envelope domain the receiving provider checked

Big organisations send through many subdomains and mail services
(em621.onepay.com, bounces via sendgrid.net), so every domain is first cut
down to its registrable domain, the part an organisation actually
registers: em621.onepay.com -> onepay.com, mail.yu.edu -> yu.edu,
news.bbc.co.uk -> bbc.co.uk. That uses the Public Suffix List bundled
with publicsuffix2, offline, with no lookups.

"Aligned" (DMARC, RFC 7489 Section 3.1, relaxed mode) means a domain
that passed SPF or DKIM has the same registrable domain as the From
address. That is what proves the From address is not borrowed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from email import policy
from email.header import decode_header, make_header
from email.parser import HeaderParser
from email.utils import getaddresses, parseaddr

from publicsuffix2 import get_sld

from engine.authresults import AuthResults
from engine.normalize import NormalizedHeaders

# Codes
ID_FROM_MISSING = "ID_FROM_MISSING"
ID_FROM_DOMAIN_INVALID = "ID_FROM_DOMAIN_INVALID"   # TLD does not exist (.iry, .glf)
ID_REPLY_TO_MISMATCH = "ID_REPLY_TO_MISMATCH"
ID_RETURN_PATH_MISMATCH = "ID_RETURN_PATH_MISMATCH"
ID_FREEMAIL_FROM = "ID_FREEMAIL_FROM"

# Free consumer mailbox providers. Real banks, agencies and schools do not
# send from these; the rules engine combines this with an institution
# claim in the display name.
FREEMAIL = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "ymail.com", "aol.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com", "icloud.com", "me.com", "mac.com",
    "proton.me", "protonmail.com", "gmx.com", "gmx.net", "mail.com", "zoho.com", "yandex.com",
}


def registrable(domain: str | None) -> str | None:
    """Registrable domain, or None when the domain has no real public suffix."""
    if not domain:
        return None
    domain = domain.strip().strip(".").lower()
    if "." not in domain:
        return None
    try:
        domain = domain.encode("idna").decode("ascii") if not domain.isascii() else domain
    except UnicodeError:
        return None
    return get_sld(domain, strict=True)


def _addr_domain(addr: str | None) -> str | None:
    if not addr or "@" not in addr:
        return None
    return addr.rsplit("@", 1)[1].strip().strip(">").lower() or None


@dataclass
class Identities:
    from_display: str = ""
    from_address: str | None = None
    from_domain: str | None = None
    from_org: str | None = None            # registrable domain of From
    reply_to: list[str] = field(default_factory=list)
    reply_to_orgs: list[str] = field(default_factory=list)
    return_path: str | None = None
    return_path_org: str | None = None
    spf_org: str | None = None
    dkim_pass_orgs: list[str] = field(default_factory=list)
    spf_aligned: bool = False
    dkim_aligned: bool = False
    codes: list[str] = field(default_factory=list)

    @property
    def aligned(self) -> bool:
        return self.spf_aligned or self.dkim_aligned


_ANGLE_ADDR = re.compile(r"<\s*([^<>\s]+@[^<>\s]+)\s*>")


def _parse_from(raw: str | None) -> tuple[str, str | None]:
    """Display name and address of the From header.

    Scammers often put a comma in an unquoted display name
    ("Microsoft account team ,_<x@evil.example>") so that standard parsers
    split it into two addresses and lose the real one. The address in
    angle brackets is what mail clients actually show and reply to, so
    that wins whenever it is present.
    """
    if not raw:
        return "", None
    m = _ANGLE_ADDR.search(raw)
    if m:
        name = raw[: m.start()].strip().strip('"').strip()
        try:
            name = str(make_header(decode_header(name)))
        except Exception:
            pass
        return name, m.group(1)
    try:
        # Handles RFC 2047 encoded names and quoted display names.
        msg = HeaderParser(policy=policy.default).parsestr(f"From: {raw}\n")
        for a in msg["From"].addresses:
            if a.addr_spec:
                return (a.display_name or "").strip(), a.addr_spec.strip()
    except Exception:
        pass
    name, addr = parseaddr(raw)
    return name.strip(), addr.strip() or None


def extract_identities(headers: NormalizedHeaders, auth: AuthResults) -> Identities:
    ids = Identities()
    ids.from_display, ids.from_address = _parse_from(headers.get("From"))
    ids.from_domain = _addr_domain(ids.from_address)
    ids.from_org = registrable(ids.from_domain)

    if not ids.from_address:
        ids.codes.append(ID_FROM_MISSING)
    elif ids.from_domain and ids.from_org is None:
        ids.codes.append(ID_FROM_DOMAIN_INVALID)

    reply_raw = ", ".join(headers.get_all("Reply-To"))
    ids.reply_to = [a for _, a in getaddresses([reply_raw]) if a]
    ids.reply_to_orgs = sorted({o for o in (registrable(_addr_domain(a)) for a in ids.reply_to) if o})

    rp = (headers.get("Return-Path") or "").strip().strip("<>").strip()
    ids.return_path = rp or None
    ids.return_path_org = registrable(_addr_domain(rp) if "@" in rp else None)

    ids.spf_org = registrable(auth.spf.domain)
    ids.dkim_pass_orgs = sorted({o for o in (registrable(d) for d in auth.dkim_pass_domains) if o})

    if ids.from_org:
        ids.spf_aligned = auth.spf.result == "pass" and ids.spf_org == ids.from_org
        ids.dkim_aligned = ids.from_org in ids.dkim_pass_orgs
        if ids.from_org in FREEMAIL:
            ids.codes.append(ID_FREEMAIL_FROM)

    # Mismatch checks still run when the From domain is fake: compare
    # against its registrable domain, or the raw domain when it has none.
    base = ids.from_org or ids.from_domain
    if base:
        reply_orgs = [registrable(_addr_domain(a)) or _addr_domain(a) for a in ids.reply_to]
        if any(o != base for o in reply_orgs):
            ids.codes.append(ID_REPLY_TO_MISMATCH)
        rp_base = ids.return_path_org or _addr_domain(ids.return_path)
        if ids.return_path is not None and rp_base != base:
            ids.codes.append(ID_RETURN_PATH_MISMATCH)
    return ids
