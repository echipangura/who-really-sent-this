import csv
from pathlib import Path

import pytest

from engine import identities as I
from engine.authresults import parse_auth_results
from engine.normalize import normalize

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _ids(text):
    n = normalize(text)
    return I.extract_identities(n, parse_auth_results(n))


STAMP = ("Received: from x by mx.google.com\n"
         "Authentication-Results: mx.google.com; dkim=pass header.i=@{d} header.s=s1;"
         " spf=pass smtp.mailfrom=b@{s}; dmarc=pass (p=REJECT) header.from={f}\n")


@pytest.mark.parametrize("domain,org", [
    ("em621.onepay.com", "onepay.com"),
    ("mail.yu.edu", "yu.edu"),
    ("news.bbc.co.uk", "bbc.co.uk"),
    ("wgmhm.iry", None),            # fake top-level domain
    ("localhost", None),
    (None, None),
])
def test_registrable(domain, org):
    assert I.registrable(domain) == org


def test_aligned_via_dkim_with_esp_return_path():
    i = _ids(STAMP.format(d="remitly.com", s="amazonses.com", f="remitly.com")
             + "Return-Path: <0101@us-west-2.amazonses.com>\nFrom: Remitly <no-reply@remitly.com>\n")
    assert i.dkim_aligned and not i.spf_aligned and i.aligned
    assert I.ID_RETURN_PATH_MISMATCH in i.codes


def test_aligned_via_spf_subdomain():
    i = _ids(STAMP.format(d="mail-yu-edu.gappssmtp.com", s="mail.yu.edu", f="mail.yu.edu")
             + "From: Someone <a@mail.yu.edu>\n")
    assert i.spf_aligned and not i.dkim_aligned


def test_reply_to_hijack():
    i = _ids(STAMP.format(d="cps.edu", s="cps.edu", f="cps.edu")
             + "From: Chicago Public Schools <payments@cps.edu>\nReply-To: cps.fee.office@gmail.com\n")
    assert I.ID_REPLY_TO_MISMATCH in i.codes and i.aligned


def test_comma_in_display_name_does_not_hide_address():
    i = _ids("From: Microsoft account team ,_<no-reply@access-accsecurity.com>\n")
    assert i.from_address == "no-reply@access-accsecurity.com"
    assert i.from_org == "access-accsecurity.com"


def test_invalid_tld_still_checks_return_path():
    i = _ids("From: someone <alert-1@wgmhm.iry>\nReturn-Path: <return@sb035.dynamicbackendhub.my.id>\n")
    assert I.ID_FROM_DOMAIN_INVALID in i.codes
    assert I.ID_RETURN_PATH_MISMATCH in i.codes


def test_freemail_from():
    i = _ids("From: [BB] Seu saldo <prestonconstance587@gmail.com>\n")
    assert I.ID_FREEMAIL_FROM in i.codes


def test_missing_from():
    assert I.ID_FROM_MISSING in _ids("Received: from a by b\n").codes


# Corpus checks: identity flags must match the hand labels in the manifest.
_FLAG_MAP = {
    "REPLY_TO_MISMATCH": I.ID_REPLY_TO_MISMATCH,
    "RETURN_PATH_MISMATCH": I.ID_RETURN_PATH_MISMATCH,
    "INVALID_FROM_DOMAIN": I.ID_FROM_DOMAIN_INVALID,
}


def _manifest():
    with (FIXTURES / "manifest.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.mark.parametrize("row", _manifest(), ids=lambda r: r["file"])
def test_corpus_identity_flags_match_labels(row):
    n = normalize((FIXTURES / row["file"]).read_text(encoding="utf-8"))
    auth = parse_auth_results(n)
    ids = I.extract_identities(n, auth)
    expected = {_FLAG_MAP[f] for f in row["expected_flags"].split(";") if f in _FLAG_MAP}
    assert {c for c in ids.codes if c in _FLAG_MAP.values()} == expected
    # Cross-check with the provider: a DMARC pass must be aligned by our math too.
    if auth.dmarc.result == "pass":
        assert ids.aligned
