"""Run the whole engine on one message and return a JSON-ready report.

This is the single entry point the interface (and the command-line tool)
calls. It returns codes and values only, never English sentences; the
interface turns codes into words through the locale files.

The report shape (SCHEMA_VERSION) is what the Streamlit app will read, so
changes to it should bump the version.
"""

from __future__ import annotations

from dataclasses import asdict

from engine.authresults import parse_auth_results
from engine.identities import extract_identities
from engine.lookalike import check_lookalike
from engine.normalize import normalize
from engine.received import build_hop_map
from engine.rules import decide
from engine.trust import find_trust_boundary

SCHEMA_VERSION = "0.4"   # 0.2: "journey"; 0.3: "impersonation"; 0.4: "verdict"


def analyze(raw: str | bytes) -> dict:
    headers = normalize(raw)
    trust = find_trust_boundary(headers)
    auth = parse_auth_results(headers, trust)
    ids = extract_identities(headers, auth)
    hops = build_hop_map(headers, trust, ids)
    look = check_lookalike(ids)

    report = {
        "schema_version": SCHEMA_VERSION,
        "normalize": {
            "header_count": len(headers.headers),
            "warnings": headers.warnings,
        },
        "trust": {
            "provider": trust.provider,
            "status": trust.status,
            "boundary_index": trust.boundary_index,
        },
        "auth": {
            "spf": asdict(auth.spf),
            "dkim": [asdict(d) for d in auth.dkim],
            "dmarc": asdict(auth.dmarc),
            "arc": auth.arc,
            "compauth": auth.compauth,
        },
        "identities": {
            "from_display": ids.from_display,
            "from_address": ids.from_address,
            "from_org": ids.from_org,
            "reply_to": ids.reply_to,
            "return_path": ids.return_path,
            "return_path_org": ids.return_path_org,
            "spf_org": ids.spf_org,
            "dkim_pass_orgs": ids.dkim_pass_orgs,
            "spf_aligned": ids.spf_aligned,
            "dkim_aligned": ids.dkim_aligned,
            "aligned": ids.aligned,
        },
        "impersonation": {
            "claimed": ({"name": look.claimed.name, "category": look.claimed.category,
                         "domains": sorted(look.claimed.domains)} if look.claimed else None),
            "imitated_domain": look.imitated_domain,
            "decoded_domain": look.decoded_domain,
        },
        "journey": {
            "hops": [{k: v for k, v in asdict(h).items() if k != "raw"} for h in hops.hops],
            "entry_number": hops.entry_number,
            "total_seconds": hops.total_seconds,
        },
        # Every code raised; rules.py (config/rules.yaml) turns them into the verdict.
        "codes": headers.warnings + ([trust.status] if trust.status != "TRUST_PROVIDER_STAMP" else []) + ids.codes + hops.codes + look.codes,
    }
    v = decide(report)
    report["verdict"] = {"tier": v.tier, "reasons": v.reasons, "notes": v.notes}
    return report
