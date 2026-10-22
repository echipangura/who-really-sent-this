"""Impersonation checks against the watchlist of frequently impersonated
institutions (brief, Section 5.3: display-name spoofing, lookalike domain,
punycode or homoglyph domain, free-mail institution claim, subdomain tricks).

Authentication (SPF, DKIM, DMARC) proves which domain sent a message. It
cannot tell whether that domain is the one the reader THINKS it is. A
scammer who registers chase-secure.com, or xn--chse-63d.com (which a mail
app shows as "chаse.com" with a Cyrillic "а"), passes every check for
their own domain. These checks compare what the reader sees with the real
institutions in data/impersonated_institutions.csv:

  Display-name spoof   the name says "U.S. Postal Service" (or contains an
                       email address) but the From domain is not theirs
  Lookalike domain     the From domain imitates a listed domain: same
                       letters after undoing look-alike characters, one or
                       two letters changed, the brand plus extra words, a
                       different ending (chase.net), or the brand hidden in
                       a subdomain (chase.com.secure-login.net)
  Punycode domain      the From domain contains xn--, an encoded
                       international name; often used for homoglyphs
  Free-mail claim      a listed institution's name, sent from Gmail, Yahoo,
                       Outlook.com and similar

Everything runs offline against the bundled CSV. Codes only.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from confusable_homoglyphs import confusables

from engine.identities import FREEMAIL, Identities, registrable

# Codes
LOOK_DISPLAY_NAME_SPOOF = "LOOK_DISPLAY_NAME_SPOOF"
LOOK_LOOKALIKE_DOMAIN = "LOOK_LOOKALIKE_DOMAIN"
LOOK_PUNYCODE_DOMAIN = "LOOK_PUNYCODE_DOMAIN"
LOOK_FREEMAIL_INSTITUTION = "LOOK_FREEMAIL_INSTITUTION"
LOOK_ADDRESS_IN_NAME = "LOOK_ADDRESS_IN_NAME"      # the display name is a different email address

WATCHLIST = Path(__file__).resolve().parent.parent / "data" / "impersonated_institutions.csv"


@dataclass(frozen=True)
class Institution:
    name: str
    domains: frozenset[str]        # registrable domains the institution really uses
    category: str
    aliases: tuple[str, ...]
    country: str = ""

    @property
    def brand_labels(self) -> set[str]:
        """'chase' from chase.com, 'bradesco' from bradesco.com.br."""
        out = set()
        for d in self.domains:
            label = _label(d)
            if label:
                out.add(label)
        return out


@dataclass
class LookalikeResult:
    claimed: Institution | None = None       # institution the message pretends to be
    imitated_domain: str | None = None       # the real domain a lookalike copies
    decoded_domain: str | None = None        # Unicode form of a punycode From domain
    codes: list[str] = field(default_factory=list)


# --- watchlist ---------------------------------------------------------------

@lru_cache(maxsize=4)
def load_watchlist(path: str | None = None) -> tuple[Institution, ...]:
    p = Path(path) if path else WATCHLIST
    out = []
    with p.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            domains = [row["domain"], *row.get("other_domains", "").split(";")]
            regs = frozenset(r for r in (registrable(d.strip()) for d in domains if d.strip()) if r)
            aliases = tuple(a.strip() for a in [row["name"], *row.get("aliases", "").split(";")] if a.strip())
            out.append(Institution(row["name"].strip(), regs, row.get("category", "").strip(),
                                   aliases, row.get("country", "").strip()))
    return tuple(out)


# --- text helpers --------------------------------------------------------------

_EXTRA_LOOKALIKES = str.maketrans({"0": "o", "1": "l", "3": "e", "5": "s", "$": "s", "@": "a"})


@lru_cache(maxsize=4096)
def skeleton(text: str) -> str:
    """Undo look-alike characters: Cyrillic 'а' -> 'a', '0' -> 'o', 'rn' -> 'm'."""
    out = []
    for ch in unicodedata.normalize("NFKC", text.lower()):
        if ord(ch) < 128:
            out.append(ch)
            continue
        hit = confusables.is_confusable(ch, preferred_aliases=["latin"], greedy=False)
        if hit and hit[0]["homoglyphs"]:
            out.append(hit[0]["homoglyphs"][0]["c"].lower())
        else:
            base = unicodedata.normalize("NFKD", ch)[:1]       # é -> e
            out.append(base if base.isascii() else ch)
    s = "".join(out).translate(_EXTRA_LOOKALIKES)
    return s.replace("rn", "m").replace("vv", "w")


def _label(domain: str) -> str | None:
    """The part an organisation picks: 'chase' in chase.com, 'bb' in bb.com.br."""
    reg = registrable(domain) or domain
    first = reg.split(".")[0] if reg else ""
    return first or None


def _decode(domain: str) -> str:
    try:
        return ".".join(lbl.encode("ascii").decode("idna") if lbl.startswith("xn--") else lbl
                        for lbl in domain.split("."))
    except UnicodeError:
        return domain


def _edit_distance(a: str, b: str, limit: int = 3) -> int:
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _display_text(name: str) -> str:
    """'US_Postal_Support®' -> 'US Postal Support'."""
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"[_\[\]()|®™©:,]+", " ", name)
    return re.sub(r"\s+", " ", name).strip()


@lru_cache(maxsize=2048)
def _alias_pattern(alias: str) -> re.Pattern:
    words = _display_text(alias)
    body = r"\s*".join(re.escape(w) for w in words.split(" "))
    # Short all-capital aliases (IRS, ICE, BB, UPS) only match in capitals,
    # so "ice cream" or "bb" in a username does not count.
    short_caps = len(words.replace(" ", "")) <= 4 and words.isupper()
    flags = 0 if short_caps else re.IGNORECASE
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", flags)


_EMAIL_IN_NAME = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")


# --- checks --------------------------------------------------------------------

def claimed_institution(display: str, watchlist=None) -> Institution | None:
    """The listed institution named in a display name, longest alias first."""
    if not display:
        return None
    text = _display_text(display)
    best, best_len = None, 0
    for inst in watchlist or load_watchlist():
        for alias in inst.aliases:
            if len(alias) > best_len and _alias_pattern(alias).search(text):
                best, best_len = inst, len(alias)
    return best


def imitated(domain: str, watchlist=None) -> tuple[Institution, str] | None:
    """The listed institution and domain that `domain` imitates, if any."""
    domain = domain.lower().strip(".")
    decoded = _decode(domain)
    reg = registrable(domain)
    if reg is None:
        return None
    insts = watchlist or load_watchlist()
    if any(reg in i.domains for i in insts):
        return None                                   # it IS a listed domain
    label = _label(reg) or ""
    sk_label = skeleton(_label(registrable(decoded) or decoded) or _decode(label))
    tokens = set(re.split(r"[-.]", skeleton(decoded)))
    for inst in insts:
        for real in sorted(inst.domains):
            rl = _label(real) or ""
            if len(rl) < 3:
                continue
            # Same letters once look-alikes are undone, or a different ending.
            if sk_label == skeleton(rl):
                return inst, real
            # One or two letters off (chasse.com, paypa1.com).
            limit = 1 if len(rl) < 7 else 2
            if len(rl) >= 5 and 0 < _edit_distance(sk_label, rl, limit) <= limit:
                return inst, real
            # Brand plus extra words (chase-secure.com, cps-edu-portal.com).
            if len(rl) >= 3 and rl in tokens and "-" in label:
                return inst, real
            # The real domain hidden at the start (chase.com.secure-login.net).
            if decoded.startswith(real + ".") or f".{real}." in f".{decoded}":
                return inst, real
    return None


def check_lookalike(ids: Identities, watchlist=None) -> LookalikeResult:
    res = LookalikeResult()
    wl = watchlist or load_watchlist()
    domain = ids.from_domain

    if domain and any(lbl.startswith("xn--") for lbl in domain.split(".")):
        res.codes.append(LOOK_PUNYCODE_DOMAIN)
        res.decoded_domain = _decode(domain)

    # Free-mail providers are real, known services, never lookalikes.
    copy = imitated(domain, wl) if domain and ids.from_org not in FREEMAIL else None
    if copy:
        res.claimed, res.imitated_domain = copy
        res.codes.append(LOOK_LOOKALIKE_DOMAIN)

    claimed = claimed_institution(ids.from_display, wl)
    from_org = ids.from_org or ids.from_domain

    # A display name that is itself an address: "service@paypal.com" <x@gmail.com>.
    m = _EMAIL_IN_NAME.search(ids.from_display or "")
    if m and from_org and (registrable(m.group(1)) or m.group(1).lower()) != from_org:
        res.codes += [LOOK_DISPLAY_NAME_SPOOF, LOOK_ADDRESS_IN_NAME]
        shown = registrable(m.group(1))
        claimed = claimed or next((i for i in wl if shown in i.domains), None)
        res.claimed = res.claimed or claimed
        if claimed and ids.from_org in FREEMAIL:
            res.codes.append(LOOK_FREEMAIL_INSTITUTION)

    # Anyone can open a free account, so a free-mail domain never counts as
    # the institution's own here, even for Microsoft (outlook.com) or Google.
    elif claimed and from_org not in (claimed.domains - FREEMAIL):
        res.claimed = res.claimed or claimed
        res.codes.append(LOOK_DISPLAY_NAME_SPOOF)
        if ids.from_org in FREEMAIL:
            res.codes.append(LOOK_FREEMAIL_INSTITUTION)
    return res
