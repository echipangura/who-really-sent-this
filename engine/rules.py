"""Turn the engine's codes into one verdict (brief, Section 5.4).

The rules themselves live in config/rules.yaml so a partner can tune them
without a developer. This module only knows how to read that file and
evaluate the small condition language it uses (all / any / not, codes and
signals). It returns codes, never sentences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

CHECKS_OUT, BE_CAREFUL, LIKELY_SCAM = "CHECKS_OUT", "BE_CAREFUL", "LIKELY_SCAM"
_RANK = {CHECKS_OUT: 0, BE_CAREFUL: 1, LIKELY_SCAM: 2}

# Always attached to a green verdict (brief 3.1: "What this tool cannot tell you").
NOTE_PASS_NOT_SAFE = "NOTE_PASS_NOT_SAFE"

RULES_FILE = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"


@dataclass
class Verdict:
    tier: str = CHECKS_OUT
    reasons: list[str] = field(default_factory=list)   # RULE_<id>, most serious first
    notes: list[str] = field(default_factory=list)


class RulesError(ValueError):
    """config/rules.yaml is malformed."""


@lru_cache(maxsize=4)
def load_rules(path: str | None = None) -> tuple[dict, ...]:
    data = yaml.safe_load(Path(path or RULES_FILE).read_text(encoding="utf-8")) or {}
    rules = data.get("rules") or []
    for r in rules:
        if not isinstance(r, dict) or {"id", "verdict", "when"} - r.keys():
            raise RulesError(f"rule needs id, verdict and when: {r!r}")
        if r["verdict"] not in (BE_CAREFUL, LIKELY_SCAM):
            raise RulesError(f"rule {r['id']}: verdict must be BE_CAREFUL or LIKELY_SCAM")
    return tuple(rules)


def signals(report: dict) -> dict[str, bool]:
    """Small-letter facts the rules can test, taken from an analyze() report."""
    auth = report["auth"]
    dmarc = (auth["dmarc"]["result"] or "").lower()
    policy = (auth["dmarc"]["policy"] or "").lower()
    return {
        "dmarc_pass": dmarc == "pass",
        "dmarc_fail": dmarc == "fail",
        "dmarc_missing": dmarc in ("", "none", "temperror", "permerror"),
        "dmarc_enforced": policy in ("quarantine", "reject"),
        "aligned": bool(report["identities"]["aligned"]),
        "spf_pass": (auth["spf"]["result"] or "").lower() == "pass",
        "dkim_pass": any((d["result"] or "").lower() == "pass" for d in auth["dkim"]),
    }


def _holds(cond, codes: set[str], sig: dict[str, bool]) -> bool:
    if isinstance(cond, str):
        if cond.islower():
            if cond not in sig:
                raise RulesError(f"unknown signal: {cond}")
            return sig[cond]
        return cond in codes
    if isinstance(cond, dict) and len(cond) == 1:
        (op, arg), = cond.items()
        if op == "all":
            return all(_holds(c, codes, sig) for c in arg)
        if op == "any":
            return any(_holds(c, codes, sig) for c in arg)
        if op == "not":
            return not _holds(arg, codes, sig)
    raise RulesError(f"cannot read condition: {cond!r}")


def decide(report: dict, rules=None) -> Verdict:
    rules = load_rules() if rules is None else rules
    codes, sig = set(report["codes"]), signals(report)
    hits = [r for r in rules if _holds(r["when"], codes, sig)]
    hits.sort(key=lambda r: -_RANK[r["verdict"]])          # stable: file order within a tier
    v = Verdict()
    if hits:
        v.tier = hits[0]["verdict"]
        v.reasons = [f"RULE_{r['id']}" for r in hits]
    else:
        v.notes.append(NOTE_PASS_NOT_SAFE)
    return v
