import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "clean_corpus", Path(__file__).resolve().parent.parent / "scripts" / "clean_corpus.py"
)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

redact = cc.build_redactor(["jane.doe@gmail.com", "jdoe1981@outlook.com", "jdoe1@icloud.com", "Jane Doe", "Jane"])


def test_full_address_and_name():
    assert redact("To: Jane Doe <jane.doe@gmail.com>") == "To: Recipient 1 <recipient1@example.com>"


def test_bounce_encoding():
    assert redact("<bounces+123-jane.doe=gmail.com@em.shop.com>") == "<bounces+123-recipient1=example.com@em.shop.com>"


def test_bare_username_longest_first():
    assert redact("To: jdoe1981, jdoe1") == "To: recipient2, recipient3"
    assert redact("<84955-jdoe1@kdia.iry>") == "<84955-recipient3@kdia.iry>"


def test_first_name_whole_word_only():
    assert redact("Subject: Jane, deals for you") == "Subject: Recipient 2, deals for you"
    assert redact("Janet") == "Janet"


def test_encoded_word():
    import base64
    enc = "=?utf-8?B?" + base64.b64encode(b"jdoe1@icloud.com").decode() + "?="
    out = redact(f"Subject: {enc}")
    assert "jdoe1" not in base64.b64decode(out.split("?")[3]).decode()
    assert out.startswith("Subject: =?utf-8?B?")


def test_provider_from_received_when_no_authserv_id():
    assert cc.detect_provider(["spf=pass smtp.mailfrom=x.com"], ["from a by MN2PR.outlook.office365.com"]) == "outlook"
    assert cc.detect_provider(["mx.google.com; spf=pass"], []) == "gmail"
