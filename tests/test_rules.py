"""Verdict rules (config/rules.yaml) and the Gate 1 check."""

from pathlib import Path

import pytest

from engine import rules as R
from engine.__main__ import evaluate
from engine.analyze import analyze

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _report(codes=(), spf="pass", dkim="pass", dmarc="pass", policy="reject", aligned=True):
    return {
        "codes": list(codes),
        "auth": {"spf": {"result": spf}, "dkim": [{"result": dkim}] if dkim else [],
                 "dmarc": {"result": dmarc, "policy": policy}},
        "identities": {"aligned": aligned},
    }


def _tier(**kw):
    return R.decide(_report(**kw)).tier


def test_clean_message_checks_out_with_note():
    v = R.decide(_report())
    assert v.tier == R.CHECKS_OUT and v.reasons == [] and v.notes == [R.NOTE_PASS_NOT_SAFE]


# Each rule: one case that triggers it, one close case that must not.
@pytest.mark.parametrize("rule,hit,miss", [
    ("DMARC_FAIL_ENFORCED",
     dict(dmarc="fail", policy="quarantine", aligned=False),
     dict(dmarc="fail", policy="none", aligned=False)),
    ("UNAUTHENTICATED_IMPERSONATION",
     dict(codes=["LOOK_DISPLAY_NAME_SPOOF", "LOOK_FREEMAIL_INSTITUTION"], spf="none", dkim="none",
          dmarc="permerror", aligned=False),
     dict(codes=["LOOK_DISPLAY_NAME_SPOOF", "LOOK_FREEMAIL_INSTITUTION"])),
    ("LOOKALIKE_INSTITUTION_DOMAIN", dict(codes=["LOOK_LOOKALIKE_DOMAIN"]), dict(codes=["ID_FREEMAIL_FROM"])),
    ("INSTITUTION_NAME_WRONG_DOMAIN",
     dict(codes=["LOOK_DISPLAY_NAME_SPOOF"]),
     dict(codes=["LOOK_DISPLAY_NAME_SPOOF", "LOOK_FREEMAIL_INSTITUTION"])),
    ("ADDRESS_DISGUISED_AS_NAME", dict(codes=["LOOK_ADDRESS_IN_NAME"]), dict()),
    ("INVALID_FROM_DOMAIN", dict(codes=["ID_FROM_DOMAIN_INVALID"]), dict()),
    ("FORGED_PROVIDER_HOP", dict(codes=["HOP_FORGED_PROVIDER"]), dict()),
    ("INCOMPLETE_HEADERS", dict(codes=["NORM_POSSIBLY_TRUNCATED"]), dict(codes=["NORM_BODY_REMOVED"])),
    ("NO_DMARC", dict(dmarc=None, policy=None), dict(dmarc="pass", policy="none")),
    ("NOT_ALIGNED", dict(aligned=False), dict()),
    ("REPLY_TO_ELSEWHERE", dict(codes=["ID_REPLY_TO_MISMATCH"]), dict(codes=["ID_RETURN_PATH_MISMATCH"])),
    ("FREEMAIL_INSTITUTION", dict(codes=["LOOK_FREEMAIL_INSTITUTION", "LOOK_DISPLAY_NAME_SPOOF"]),
     dict(codes=["ID_FREEMAIL_FROM"])),
    ("UNRELATED_FIRST_SERVER", dict(codes=["HOP_ENTRY_UNRELATED"]), dict()),
    ("ODD_ROUTE", dict(codes=["HOP_LONG_DELAY"]), dict(codes=["HOP_MALFORMED"])),
])
def test_rule_positive_and_negative(rule, hit, miss):
    assert f"RULE_{rule}" in R.decide(_report(**hit)).reasons
    assert f"RULE_{rule}" not in R.decide(_report(**miss)).reasons


def test_most_serious_verdict_wins_and_reasons_are_ordered():
    v = R.decide(_report(codes=["ID_REPLY_TO_MISMATCH", "LOOK_LOOKALIKE_DOMAIN"]))
    assert v.tier == R.LIKELY_SCAM
    assert v.reasons[0] == "RULE_LOOKALIKE_INSTITUTION_DOMAIN" and "RULE_REPLY_TO_ELSEWHERE" in v.reasons


def test_return_path_or_personal_freemail_alone_do_not_downgrade():
    assert _tier(codes=["ID_RETURN_PATH_MISMATCH", "ID_FREEMAIL_FROM"], policy="none") == R.CHECKS_OUT


def test_spf_none_with_aligned_dkim_still_checks_out():
    assert _tier(spf="none") == R.CHECKS_OUT


def test_malformed_rules_are_rejected():
    with pytest.raises(R.RulesError):
        R.decide(_report(), rules=({"id": "X", "verdict": "BE_CAREFUL", "when": {"any": ["made_up"]}},))
    with pytest.raises(R.RulesError):
        R.decide(_report(), rules=({"id": "X", "verdict": "BE_CAREFUL", "when": {"maybe": []}},))


def test_rules_file_loads():
    ids = [r["id"] for r in R.load_rules()]
    assert len(ids) == len(set(ids)) >= 10


def test_every_fixture_gets_a_verdict():
    for p in FIXTURES.glob("*.eml"):
        assert analyze(p.read_bytes())["verdict"]["tier"] in (R.CHECKS_OUT, R.BE_CAREFUL, R.LIKELY_SCAM)


def test_gate_1():
    # Brief, Gate 1: at least 90% verdict agreement with the hand labels,
    # and no "Likely a scam" verdict on any legitimate sample.
    r = evaluate(FIXTURES)
    assert r["agree"] / r["total"] >= 0.90, r["misses"]
    assert r["legit_red"] == []
