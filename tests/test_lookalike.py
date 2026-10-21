import csv
from pathlib import Path

import pytest

from engine import lookalike as L
from engine.authresults import parse_auth_results
from engine.identities import extract_identities
from engine.normalize import normalize

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _look(from_line):
    n = normalize(f"Received: from a by mx.google.com\nFrom: {from_line}\n")
    return L.check_lookalike(extract_identities(n, parse_auth_results(n)))


def test_watchlist_has_100_plus_rows_with_real_domains():
    wl = L.load_watchlist()
    assert len(wl) >= 100
    assert all(i.domains for i in wl), [i.name for i in wl if not i.domains]


def test_skeleton_undoes_lookalike_characters():
    assert L.skeleton("chаse") == "chase"          # Cyrillic а
    assert L.skeleton("paypa1") == "paypal"
    assert L.skeleton("rnicrosoft") == "microsoft"


@pytest.mark.parametrize("domain,real", [
    ("xn--chse-63d.com", "chase.com"),     # homoglyph (punycode)
    ("paypa1.com", "paypal.com"),          # digit for a letter
    ("chasse.com", "chase.com"),           # one letter added
    ("chase.net", "chase.com"),            # different ending
    ("chase-secure.com", "chase.com"),     # brand plus extra words
    ("cps-edu-portal.com", "cps.edu"),     # the brief's own example
    ("chase.com.secure-login.net", "chase.com"),  # brand hidden in a subdomain
    ("rnicrosoft.com", "microsoft.com"),
])
def test_lookalike_domains(domain, real):
    hit = L.imitated(domain)
    assert hit and hit[1] == real


@pytest.mark.parametrize("domain", [
    "chase.com", "alerts.chase.com", "em.paypal.com",   # the real thing
    "slack.com", "uber.com", "github.com", "remitly.com", "utest.com",
])
def test_real_and_unrelated_domains_are_not_lookalikes(domain):
    assert L.imitated(domain) is None


def test_display_name_spoof():
    r = _look("U.S. Postal Service <admin@hash.asha-es.com>")
    assert L.LOOK_DISPLAY_NAME_SPOOF in r.codes and r.claimed.name == "U.S. Postal Service"
    assert _look("US_Postal_Support® <x@i.softbank.jp>").claimed.name == "U.S. Postal Service"


def test_real_sender_is_not_a_spoof():
    assert _look("Chase <alerts@chase.com>").codes == []
    assert _look("Microsoft account team <x@accountprotection.microsoft.com>").codes == []


def test_freemail_institution_even_for_providers_own_brand():
    r = _look("Microsoft account team <helpdesk.ms@outlook.com>")
    assert {L.LOOK_DISPLAY_NAME_SPOOF, L.LOOK_FREEMAIL_INSTITUTION} <= set(r.codes)


def test_email_address_as_display_name():
    r = _look('"service@paypal.com" <help.desk.4471@gmail.com>')
    assert r.claimed.name == "PayPal"
    assert {L.LOOK_DISPLAY_NAME_SPOOF, L.LOOK_FREEMAIL_INSTITUTION} <= set(r.codes)


def test_short_aliases_need_capitals():
    assert _look("ice cream deals <a@shop-example.com>").codes == []
    assert L.LOOK_DISPLAY_NAME_SPOOF in _look("ICE Notice <a@shop-example.com>").codes


def test_ordinary_people_are_not_institutions():
    assert _look("Recipient 1 <recipient1@gmail.com>").codes == []
    assert _look("Fritz Construction <hr@fritconstructioninc.com>").codes == []


def test_punycode_flag_and_decoding():
    r = _look("Chase <alerts@xn--chse-63d.com>")
    assert {L.LOOK_PUNYCODE_DOMAIN, L.LOOK_LOOKALIKE_DOMAIN, L.LOOK_DISPLAY_NAME_SPOOF} <= set(r.codes)
    assert r.decoded_domain == "chаse.com"


# --- corpus ----------------------------------------------------------------

_MAP = {
    "DISPLAY_NAME_SPOOF": L.LOOK_DISPLAY_NAME_SPOOF,
    "LOOKALIKE_DOMAIN": L.LOOK_LOOKALIKE_DOMAIN,
    "PUNYCODE_DOMAIN": L.LOOK_PUNYCODE_DOMAIN,
    "FREEMAIL_INSTITUTION": L.LOOK_FREEMAIL_INSTITUTION,
}


def _manifest():
    with (FIXTURES / "manifest.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.mark.parametrize("row", _manifest(), ids=lambda r: r["file"])
def test_corpus_impersonation_flags_match_labels(row):
    n = normalize((FIXTURES / row["file"]).read_text(encoding="utf-8"))
    r = L.check_lookalike(extract_identities(n, parse_auth_results(n)))
    expected = {_MAP[f] for f in row["expected_flags"].split(";") if f in _MAP}
    assert set(r.codes) == expected
