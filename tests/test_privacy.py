"""The privacy section and the promises it makes (brief, Gate 3).

These tests guard the promise in plain words: nothing pasted is stored,
sent or looked up, and the check still works without the reader's own
address.
"""

import ast
import re
from pathlib import Path

import pytest

from engine import i18n
from engine.analyze import analyze

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

# Modules that would let the app talk to the network or keep a record.
FORBIDDEN = {"requests", "urllib", "http", "socket", "dns", "smtplib", "logging", "sqlite3", "shelve"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize("path", [ROOT / "app.py", *sorted((ROOT / "engine").glob("*.py"))],
                         ids=lambda p: p.name)
def test_no_network_or_storage_modules(path):
    assert not (_imports(path) & FORBIDDEN)


def test_usage_statistics_are_off():
    assert re.search(r"gatherUsageStats\s*=\s*false", (ROOT / ".streamlit" / "config.toml").read_text())


def _without_recipient(raw: str) -> str:
    out, skip = [], False
    for line in raw.split("\n"):
        if re.match(r"(?i)^(to|delivered-to|cc|x-original-to):", line):
            skip = True
            continue
        if skip and line[:1] in (" ", "\t"):
            continue
        skip = False
        out.append(line)
    return "\n".join(out)


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.eml")), ids=lambda p: p.name)
def test_removing_your_own_address_keeps_the_verdict(path):
    raw = path.read_text(encoding="utf-8", errors="replace")
    assert analyze(_without_recipient(raw))["verdict"]["tier"] == analyze(raw)["verdict"]["tier"]


@pytest.mark.parametrize("lang", ["en", "es"])
def test_privacy_text_exists_and_fills_in(lang):
    text = i18n.t("privacy.text", lang, hosting_url="https://h.example", code_url="https://c.example")
    assert "https://h.example" in text and "https://c.example" in text
    assert "{" not in text


@pytest.mark.parametrize("lang", ["en", "es"])
def test_app_shows_privacy_section(lang):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    if lang == "es":
        at.radio[0].set_value("es").run()
    labels = [e.label for e in at.expander]
    assert any(i18n.t("privacy.title", lang) in label for label in labels)
    assert not at.exception
