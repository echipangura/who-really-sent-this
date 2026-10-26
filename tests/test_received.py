import csv
from pathlib import Path

import pytest

from engine import received as R
from engine.authresults import parse_auth_results
from engine.identities import extract_identities
from engine.normalize import normalize
from engine.trust import find_trust_boundary

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _map(text):
    n = normalize(text)
    t = find_trust_boundary(n)
    return R.build_hop_map(n, t, extract_identities(n, parse_auth_results(n, t)))


# --- parsing one Received line, one style per provider -------------------

def test_parse_gmail_style():
    h = R.parse_received(
        "from vsin80p3283.jpmchase.com (vsin80p3283.jpmchase.com. [146.143.8.26]) "
        "by mx.google.com with ESMTPS id abc for <a@gmail.com>; Sat, 5 Sep 2026 08:49:01 -0700 (PDT)")
    assert (h.from_host, h.from_ptr, h.from_ip, h.by_host, h.protocol) == (
        "vsin80p3283.jpmchase.com", "vsin80p3283.jpmchase.com", "146.143.8.26", "mx.google.com", "ESMTPS")
    assert h.timestamp == "2026-09-05T15:49:01+00:00"


def test_parse_outlook_style_bare_ip_in_comment():
    h = R.parse_received(
        "from ubuntu-s-1vcpu (137.184.34.4) by BN8NAM11FT066.mail.protection.outlook.com "
        "(10.13.177.138) with Microsoft SMTP Server id 15.20; Tue, 19 Sep 2023 18:36:44 +0000")
    assert h.from_host == "ubuntu-s-1vcpu" and h.from_ip == "137.184.34.4"
    assert h.by_host == "bn8nam11ft066.mail.protection.outlook.com"


def test_parse_yahoo_ehlo_style():
    h = R.parse_received("from 108.174.6.195 (EHLO maile-cc.linkedin.com) by 10.200.73.56 "
                         "with SMTPs (version=TLS1_3); Thu, 24 Sep 2026 01:51:42 +0000")
    assert h.from_host == "maile-cc.linkedin.com" and h.from_ip == "108.174.6.195"


def test_parse_date_without_semicolon():
    # SendGrid internal hops put the date straight after the id.
    h = R.parse_received("from MzY4 (unknown) by geopod-ismtpd-11 (SG) with HTTP id WA-1 "
                         "Sat, 19 Sep 2026 04:12:46.360 +0000 (UTC)")
    assert h.timestamp == "2026-09-19T04:12:46+00:00"
    h = R.parse_received("by recvd-79c with SMTP id recvd-1 2026-09-19 04:12:46.39437255 +0000 UTC m=+8.2")
    assert h.timestamp == "2026-09-19T04:12:46+00:00"


def test_parse_never_raises_on_junk():
    h = R.parse_received("garbage ((( [not-an-ip] ;;; not a date")
    assert h.timestamp is None


# --- the map ---------------------------------------------------------------

GMAIL = (
    "Received: by 2002:a05:7412::1 with SMTP id x; Sat, 5 Sep 2026 08:49:02 -0700\n"
    "Received: from out.examplebank.com (out.examplebank.com. [192.0.2.10]) by mx.google.com with ESMTPS id y;"
    " Sat, 5 Sep 2026 08:49:01 -0700\n"
    "Authentication-Results: mx.google.com; spf=pass (google.com: domain of a@examplebank.com designates"
    " 192.0.2.10 as permitted sender) smtp.mailfrom=a@examplebank.com; dmarc=pass header.from=examplebank.com\n"
    "Received: from inner.examplebank.com ([10.0.0.5]) by out.examplebank.com with ESMTP id z;"
    " Sat, 5 Sep 2026 15:49:00 +0000\n"
    "From: Bank <a@examplebank.com>\n"
)


def test_chronological_order_and_trust():
    hm = _map(GMAIL)
    assert [h.number for h in hm.hops] == [1, 2, 3]
    assert hm.hops[0].by_host == "out.examplebank.com"          # oldest first
    assert hm.entry_number == 2 and hm.entry.from_ip == "192.0.2.10"
    assert [h.trusted for h in hm.hops] == [False, True, True]
    assert [h.delay_seconds for h in hm.hops] == [None, 1, 1]
    assert hm.total_seconds == 2 and hm.codes == []


def test_forged_provider_hop_below_entry():
    text = GMAIL.replace(
        "Received: from inner.examplebank.com",
        "Received: from x-sender.net (x-sender.net. [198.51.100.1]) by mx.google.com with ESMTPS id q;"
        " Sat, 5 Sep 2026 15:48:00 +0000\nReceived: from inner.examplebank.com")
    assert R.HOP_FORGED_PROVIDER in _map(text).codes


def test_time_reversed_and_long_delay():
    back = GMAIL.replace("Sat, 5 Sep 2026 15:49:00 +0000", "Sat, 5 Sep 2026 17:00:00 +0000")
    assert R.HOP_TIME_REVERSED in _map(back).codes
    late = GMAIL.replace("Sat, 5 Sep 2026 15:49:00 +0000", "Wed, 2 Sep 2026 15:49:00 +0000")
    assert R.HOP_LONG_DELAY in _map(late).codes


def test_small_clock_skew_is_fine():
    skew = GMAIL.replace("Sat, 5 Sep 2026 15:49:00 +0000", "Sat, 5 Sep 2026 15:55:00 +0000")
    assert _map(skew).codes == []


def test_entry_unrelated_only_when_not_aligned():
    spoof = GMAIL.replace("From: Bank <a@examplebank.com>", "From: IRS <notice@irs.gov>").replace(
        "spf=pass", "spf=fail").replace("dmarc=pass", "dmarc=fail")
    assert R.HOP_ENTRY_UNRELATED in _map(spoof).codes
    # A mail service (here out.examplebank.com) sending for an aligned domain is normal.
    esp = GMAIL.replace("From: Bank <a@examplebank.com>", "From: Shop <news@exampleshop.com>").replace(
        "dmarc=pass", "dkim=pass header.i=@exampleshop.com; dmarc=pass")
    assert R.HOP_ENTRY_UNRELATED not in _map(esp).codes


def test_helo_alone_does_not_vouch_when_spf_fails():
    # "EHLO online.de" from an IP online.de never authorised (phish_wild_011).
    text = ("Received: from 127.0.0.1 by atlas.mail.yahoo.com with HTTP; Sun, 25 Oct 2026 21:20:13 +0000\n"
            "Authentication-Results: mta.yahoo.com; spf=softfail smtp.mailfrom=online.de;"
            " dmarc=fail(p=NONE) header.from=online.de\n"
            "Received: from 92.71.249.74 (EHLO online.de) by 10.200.77.175 with SMTP;"
            " Sun, 25 Oct 2026 21:20:13 +0000\n"
            "From: Emily <someone@online.de>\n")
    assert R.HOP_ENTRY_UNRELATED in _map(text).codes
    # The same HELO with SPF passing is backed up, so no flag.
    ok = text.replace("spf=softfail", "spf=pass").replace("dmarc=fail(p=NONE)", "dmarc=pass(p=NONE)")
    assert R.HOP_ENTRY_UNRELATED not in _map(ok).codes


def test_no_received():
    assert _map("From: a@b.com\nSubject: hi\n").codes == [R.HOP_NONE]


def test_malformed_line():
    assert R.HOP_MALFORMED in _map(GMAIL + "Received: from somewhere\n").codes


# --- corpus ----------------------------------------------------------------

_HOP_CODES = {R.HOP_FORGED_PROVIDER, R.HOP_ENTRY_UNRELATED, R.HOP_TIME_REVERSED,
              R.HOP_LONG_DELAY, R.HOP_MALFORMED}


def _manifest():
    with (FIXTURES / "manifest.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.mark.parametrize("row", _manifest(), ids=lambda r: r["file"])
def test_corpus_hop_flags_match_labels(row):
    hm = _map((FIXTURES / row["file"]).read_text(encoding="utf-8"))
    labelled = "HOP_ANOMALY" in row["expected_flags"].split(";")
    assert bool(set(hm.codes) & _HOP_CODES) == labelled, hm.codes
    if hm.hops:
        assert hm.entry is not None and hm.entry.trusted
        assert hm.hops[-1].trusted                     # the inbox end is always the provider
