import csv
from pathlib import Path

import pytest

from engine import trust as T
from engine.authresults import parse_auth_results, split_segments
from engine.normalize import normalize

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _auth(text):
    n = normalize(text)
    return T.find_trust_boundary(n), parse_auth_results(n)


GMAIL = (
    "Delivered-To: r@example.com\n"
    "Received: by 2002:a05::1 with SMTP id x; Mon, 5 Oct 2026 08:00:01 -0700\n"
    "Received: from mail.chase.com by mx.google.com with ESMTPS id y\n"
    "Authentication-Results: mx.google.com; dkim=pass header.i=@chase.com header.s=d4815 header.b=abc;"
    " spf=pass (google.com: domain of a@chase.com designates 1.2.3.4 as permitted sender)"
    " smtp.mailfrom=a@chase.com; dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=chase.com\n"
    "From: Chase <a@chase.com>\n"
)


def test_gmail_stamp():
    t, a = _auth(GMAIL)
    assert (t.provider, t.status) == ("gmail", T.TRUST_PROVIDER_STAMP)
    assert (a.spf.result, a.spf.domain) == ("pass", "chase.com")
    assert [(d.result, d.domain, d.selector) for d in a.dkim] == [("pass", "chase.com", "d4815")]
    assert (a.dmarc.result, a.dmarc.policy, a.dmarc.header_from) == ("pass", "reject", "chase.com")


def test_forged_stamp_below_is_ignored():
    # A sender can type a fake passing stamp into the message; it ends up
    # below the provider's real one and must not be used.
    forged = GMAIL.replace(
        "From: Chase",
        "Authentication-Results: mx.google.com; spf=pass smtp.mailfrom=x@bank.com; dmarc=pass header.from=bank.com\n"
        "From: Chase",
    )
    real = forged.replace("dmarc=pass (p=REJECT", "dmarc=fail (p=REJECT")
    _, a = _auth(real)
    assert a.dmarc.result == "fail"
    assert a.dmarc.header_from == "chase.com"


def test_outlook_stamp_and_arc_policy():
    text = (
        "Received: from A.prod.outlook.com by B.prod.outlook.com with HTTPS\n"
        "ARC-Authentication-Results: i=2; mx.microsoft.com 1; spf=pass smtp.mailfrom=gmail.com;"
        " dmarc=pass (p=none sp=quarantine pct=100) action=none header.from=gmail.com; dkim=pass header.d=gmail.com\n"
        "Authentication-Results: mx.microsoft.com 1; spf=pass (sender IP is 1.2.3.4) smtp.mailfrom=gmail.com;"
        " dkim=pass (signature was verified) header.d=gmail.com;dmarc=pass action=none"
        " header.from=gmail.com;compauth=pass reason=100\n"
        "From: x@gmail.com\n"
    )
    t, a = _auth(text)
    assert t.provider == "outlook"
    assert a.dmarc.result == "pass" and a.dmarc.policy == "none"
    assert a.compauth == "pass"
    assert a.dkim[0].domain == "gmail.com"


def test_outlook_nameless_stamp_and_unsigned():
    text = (
        "Received: from x.namprd19.prod.outlook.com (::1) by MN0PR.namprd19.prod.outlook.com with HTTPS\n"
        "Authentication-Results: spf=none (sender IP is 89.144.44.2) smtp.mailfrom=thcultarfdes.co.uk;"
        " dkim=none (message not signed) header.d=none;dmarc=permerror action=none header.from=access-accsecurity.com;\n"
        "From: x@access-accsecurity.com\n"
    )
    t, a = _auth(text)
    assert t.provider == "outlook"
    assert a.spf.result == "none"
    assert a.dkim[0].result == "none" and a.dkim[0].domain is None
    assert a.dmarc.result == "permerror"


def test_yahoo_policy_without_space():
    text = (
        "Received: from 127.0.0.1 by atlas.yahoo.com with HTTP\n"
        "Authentication-Results: mta.yahoo.com; dkim=pass header.i=@remitly.com header.s=k1"
        " arc_overridden_status=NOT_OVERRIDDEN; spf=pass smtp.mailfrom=amazonses.com;"
        " dmarc=pass(p=REJECT,sp=REJECT) header.from=remitly.com\n"
        "From: no-reply@remitly.com\n"
    )
    t, a = _auth(text)
    assert t.provider == "yahoo"
    assert a.dmarc.policy == "reject" and a.spf.domain == "amazonses.com"


def test_icloud_split_stamps_and_policy_header():
    text = (
        "Received: from a.apple.com by p00-icloudmta\n"
        "Authentication-Results: dmarc.icloud.com; dmarc=pass header.from=email.apple.com\n"
        "X-DMARC-Info: pass=pass; dmarc-policy=reject; s=r1; d=r1; pdomain=email.apple.com\n"
        "Authentication-Results: dkim-verifier.icloud.com; dkim=pass header.d=email.apple.com\n"
        "Authentication-Results: spf.icloud.com; spf=pass smtp.mailfrom=noreply@email.apple.com\n"
        "Authentication-Results: dmarc.icloud.com; dmarc=fail header.from=forged.example\n"
        "From: Apple <noreply@email.apple.com>\n"
    )
    t, a = _auth(text)
    assert t.provider == "icloud" and len(t.stamps) == 3  # duplicate dmarc line ignored
    assert (a.dmarc.result, a.dmarc.policy) == ("pass", "reject")
    assert a.spf.domain == "email.apple.com"


def test_no_stamp():
    t, a = _auth("Received: from a by b\nFrom: x@example.org\n")
    assert t.status == T.TRUST_NO_STAMP and a.dmarc.result is None


def test_split_ignores_semicolons_in_comments():
    assert split_segments("a; spf=pass (x; y) smtp.mailfrom=z; dmarc=pass") == [
        "a", "spf=pass (x; y) smtp.mailfrom=z", "dmarc=pass"]


def _manifest():
    with (FIXTURES / "manifest.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.mark.parametrize("row", _manifest(), ids=lambda r: r["file"])
def test_corpus_provider_detected(row):
    n = normalize((FIXTURES / row["file"]).read_text(encoding="utf-8"))
    t = T.find_trust_boundary(n)
    assert t.provider == row["provider"]
    a = parse_auth_results(n, t)
    # Every real sample with a stamp yields at least an SPF or DKIM result.
    if t.status != T.TRUST_NO_STAMP:
        assert a.spf.result or a.dkim
