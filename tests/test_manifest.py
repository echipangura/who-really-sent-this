"""Keep the labeled corpus consistent: every fixture is labeled, and
every label uses a known verdict and known flag codes."""

import csv
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
VERDICTS = {"CHECKS_OUT", "BE_CAREFUL", "LIKELY_SCAM"}
FLAGS = {
    "DISPLAY_NAME_SPOOF", "LOOKALIKE_DOMAIN", "PUNYCODE_DOMAIN", "REPLY_TO_MISMATCH",
    "RETURN_PATH_MISMATCH", "FREEMAIL_INSTITUTION", "HOP_ANOMALY", "NO_DMARC_POLICY",
    "INVALID_FROM_DOMAIN",
}


def _rows():
    with (FIXTURES / "manifest.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_every_fixture_is_in_manifest_and_back():
    listed = {r["file"] for r in _rows()}
    on_disk = {p.name for p in FIXTURES.glob("*.eml")}
    assert listed == on_disk


def test_labels_use_known_codes():
    for r in _rows():
        assert r["expected_verdict"] in VERDICTS, r["file"]
        flags = [f for f in r["expected_flags"].split(";") if f]
        assert set(flags) <= FLAGS, r["file"]


def test_no_scam_label_on_legitimate_set():
    # Gate 1: zero "Likely a scam" verdicts on the legitimate set.
    assert not [r["file"] for r in _rows() if r["file"].startswith("legit") and r["expected_verdict"] == "LIKELY_SCAM"]
