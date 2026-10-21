import json
from pathlib import Path

from engine.__main__ import main
from engine.analyze import SCHEMA_VERSION, analyze

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_analyze_report_shape():
    r = analyze((FIXTURES / "legit_gmail_001.eml").read_bytes())
    assert r["schema_version"] == SCHEMA_VERSION
    assert r["trust"]["provider"] == "gmail"
    assert r["auth"]["dmarc"]["result"] == "pass"
    assert r["identities"]["from_org"] == "chase.com"
    assert r["identities"]["aligned"] is True


def test_every_fixture_produces_json():
    for p in FIXTURES.glob("*.eml"):
        json.dumps(analyze(p.read_bytes()))


def test_cli_analyze_prints_json(capsys):
    assert main(["analyze", str(FIXTURES / "phish_wild_009.eml")]) == 0
    out = json.loads(capsys.readouterr().out)
    assert "ID_FROM_DOMAIN_INVALID" in out["codes"]


def test_cli_summary(capsys):
    assert main(["summary", str(FIXTURES)]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1 + len(list(FIXTURES.glob("*.eml")))
