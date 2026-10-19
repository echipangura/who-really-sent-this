"""Read SPF, DKIM, DMARC and ARC results from the trusted stamp
(brief, Section 5.2 step 4; RFC 8601).

Each provider writes the same information a little differently:

  Gmail    dkim=pass header.i=@chase.com header.s=d4815; spf=pass (google.com:
           ...) smtp.mailfrom=alerts@chase.com; dmarc=pass (p=REJECT sp=REJECT
           dis=NONE) header.from=chase.com
  Outlook  spf=pass (sender IP is 1.2.3.4) smtp.mailfrom=gmail.com; dkim=pass
           (signature was verified) header.d=gmail.com;dmarc=pass action=none
           header.from=gmail.com;compauth=pass reason=100
  Yahoo    dkim=pass header.i=@x.com header.s=s1 arc_overridden_status=...;
           dmarc=pass(p=REJECT,sp=REJECT) header.from=x.com
  iCloud   one line per check (dmarc.icloud.com; dmarc=pass header.from=...)
           with the policy in X-DMARC-Info / X-DMARC-Policy

So this is a tolerant parser rather than a strict RFC one: it splits on
";" outside parentheses, reads "method=result", then any "ptype.property=
value" pairs, and pulls the DMARC policy (p=) from wherever that provider
put it. Pure standard library, so it runs in the browser build too.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from engine.normalize import NormalizedHeaders
from engine.trust import ICLOUD, OUTLOOK, TrustInfo, authserv_id, find_trust_boundary

_METHOD = re.compile(r"^\s*([a-z][a-z0-9_-]*)\s*=\s*([a-z]+)", re.I)
_PROP = re.compile(r"\b((?:header|smtp|policy)\.[a-z-]+)\s*=\s*(\"[^\"]*\"|[^\s;()]+)", re.I)
_POLICY = re.compile(r"(?<![a-z])p\s*=\s*([a-z]+)", re.I)
_DMARC_INFO_POLICY = re.compile(r"dmarc-policy\s*=\s*([a-z]+)", re.I)


@dataclass
class SpfResult:
    result: str | None = None   # pass, fail, softfail, neutral, none, temperror, permerror
    domain: str | None = None   # the envelope (Return-Path) domain that was checked


@dataclass
class DkimResult:
    result: str
    domain: str | None = None   # the d= domain that signed
    selector: str | None = None


@dataclass
class DmarcResult:
    result: str | None = None   # None means the stamp has no DMARC result at all
    policy: str | None = None   # none, quarantine, reject (lowercase)
    header_from: str | None = None


@dataclass
class AuthResults:
    provider: str
    trust_status: str
    spf: SpfResult = field(default_factory=SpfResult)
    dkim: list[DkimResult] = field(default_factory=list)
    dmarc: DmarcResult = field(default_factory=DmarcResult)
    arc: str | None = None
    compauth: str | None = None  # Microsoft's own combined verdict

    @property
    def dkim_pass_domains(self) -> list[str]:
        return [d.domain for d in self.dkim if d.result == "pass" and d.domain]


def split_segments(value: str) -> list[str]:
    """Split an Authentication-Results value on ';' outside parentheses."""
    parts, depth, cur = [], 0, []
    for ch in value:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == ";" and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


def _props(segment: str) -> dict[str, str]:
    # Properties never live inside comments; drop comments first.
    no_comments = re.sub(r"\([^()]*\)", " ", segment)
    return {k.lower(): v.strip('"') for k, v in _PROP.findall(no_comments)}


def _domain(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().strip("<>").strip('"')
    domain = value.rsplit("@", 1)[-1].lower().rstrip(".")
    # Microsoft writes header.d=none when nothing was signed.
    return None if domain in ("", "none", "null") else domain


def _parse_stamp(value: str, out: AuthResults) -> None:
    segments = split_segments(value)
    if segments and authserv_id(value):
        segments = segments[1:]  # drop the authserv-id
    for seg in segments:
        m = _METHOD.match(seg)
        if not m:
            continue
        method, result = m.group(1).lower(), m.group(2).lower()
        props = _props(seg)
        if method == "spf" and out.spf.result is None:
            out.spf = SpfResult(result, _domain(props.get("smtp.mailfrom")))
        elif method == "dkim":
            out.dkim.append(DkimResult(
                result,
                _domain(props.get("header.d") or props.get("header.i")),
                props.get("header.s"),
            ))
        elif method == "dmarc" and out.dmarc.result is None:
            pol = _POLICY.search(seg)
            out.dmarc = DmarcResult(result, pol.group(1).lower() if pol else None,
                                    _domain(props.get("header.from")))
        elif method == "arc" and out.arc is None:
            out.arc = result
        elif method == "compauth" and out.compauth is None:
            out.compauth = result


def _fill_policy(headers: NormalizedHeaders, trust: TrustInfo, out: AuthResults) -> None:
    """Find the DMARC policy when the stamp itself does not show it."""
    if out.dmarc.result is None or out.dmarc.policy:
        return
    if trust.provider == OUTLOOK:
        # Microsoft puts p= in its own ARC-Authentication-Results (topmost).
        # Its value looks like "i=2; mx.microsoft.com 1; spf=...; dmarc=pass
        # (p=none sp=quarantine pct=100) ...".
        for v in headers.get_all("ARC-Authentication-Results"):
            segs = split_segments(v)
            if len(segs) < 2 or not segs[1].lower().startswith("mx.microsoft.com"):
                continue
            for seg in segs[2:]:
                if seg.lower().startswith("dmarc="):
                    m = _POLICY.search(seg)
                    if m:
                        out.dmarc.policy = m.group(1).lower()
            return  # only the topmost Microsoft ARC stamp counts
    if trust.provider == ICLOUD:
        info = headers.get("X-DMARC-Info") or ""
        m = _DMARC_INFO_POLICY.search(info) or _POLICY.search(headers.get("X-DMARC-Policy") or "")
        if m:
            out.dmarc.policy = m.group(1).lower()


def parse_auth_results(headers: NormalizedHeaders, trust: TrustInfo | None = None) -> AuthResults:
    """Authentication results as reported by the receiving provider only."""
    trust = trust or find_trust_boundary(headers)
    out = AuthResults(provider=trust.provider, trust_status=trust.status)
    for stamp in trust.stamps:
        _parse_stamp(stamp, out)
    _fill_policy(headers, trust, out)
    return out
