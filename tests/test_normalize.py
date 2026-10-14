from engine import normalize as N
from engine.normalize import normalize

GMAIL = (
    "Delivered-To: recipient1@example.com\r\n"
    "Received: by 2002:a05:6a10:1234 with SMTP id abc;\r\n"
    "        Mon, 5 Oct 2026 08:00:01 -0700 (PDT)\r\n"
    "Authentication-Results: mx.google.com;\r\n"
    "       dkim=pass header.i=@chase.com header.s=s1;\r\n"
    "       spf=pass smtp.mailfrom=alerts@chase.com;\r\n"
    "       dmarc=pass (p=REJECT) header.from=chase.com\r\n"
    "From: Chase <alerts@chase.com>\r\n"
    "Subject: Your statement is ready\r\n"
    "\r\n"
    "Hello, this is the body.\r\n"
)


def test_unfolds_and_handles_crlf():
    n = normalize(GMAIL)
    ar = n.get("Authentication-Results")
    assert ar == ("mx.google.com; dkim=pass header.i=@chase.com header.s=s1; "
                  "spf=pass smtp.mailfrom=alerts@chase.com; dmarc=pass (p=REJECT) header.from=chase.com")
    assert "\r" not in n.text
    assert n.get("Received").endswith("(PDT)")


def test_drops_body_and_warns():
    n = normalize(GMAIL)
    assert "body" not in n.text
    assert N.BODY_REMOVED in n.warnings


def test_clean_headers_have_no_warnings():
    headers_only = GMAIL.split("\r\n\r\n")[0]
    assert normalize(headers_only).warnings == []


def test_skips_gmail_show_original_summary():
    pasted = (
        "Original message\n"
        "Message ID\t<abc@chase.com>\n"
        "Created at:\tMon, Oct 5, 2026 at 8:00 AM\n"
        "SPF:\tPASS with IP 1.2.3.4 Learn more\n"
        "DKIM:\t'PASS' with domain chase.com Learn more\n"
        "\n" + GMAIL
    )
    n = normalize(pasted)
    assert N.LEADING_TEXT_REMOVED in n.warnings
    assert n.headers[0][0] == "Delivered-To"
    assert n.get("SPF") is None


def test_bytes_and_bom():
    n = normalize(b"\xef\xbb\xbf" + GMAIL.encode())
    assert n.headers[0][0] == "Delivered-To"


def test_lost_indentation_is_joined_not_dropped():
    pasted = "Received: from mail.example.org\nby mx.google.com with ESMTPS\nFrom: a@example.org\n"
    n = normalize(pasted)
    assert n.get("Received") == "from mail.example.org by mx.google.com with ESMTPS"
    assert N.MALFORMED_LINE_JOINED in n.warnings


def test_nothing_header_like():
    n = normalize("Hi, can you check this email for me?")
    assert n.headers == []
    assert n.warnings == [N.NO_HEADERS_FOUND]


def test_truncated_paste_flagged():
    n = normalize("Received: from a by b; Mon, 5 Oct 2026 08:00:01 -0700\nAuthentication-Results: mx.google.com; spf=pass")
    assert N.MISSING_FROM in n.warnings
    assert N.POSSIBLY_TRUNCATED in n.warnings


def test_missing_auth_results_flagged():
    n = normalize("Received: from a by b\nFrom: x@example.org\n")
    assert N.MISSING_AUTH_RESULTS in n.warnings


def test_parses_with_stdlib():
    msg = normalize(GMAIL).to_message()
    assert msg["From"].addresses[0].domain == "chase.com"
    assert len(msg.get_all("Received")) == 1
