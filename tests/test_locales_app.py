"""Locale strings and the Streamlit app (brief: engine emits codes, the
interface renders words; English verdict text at or below grade 6)."""

import json
import re
from pathlib import Path

import pytest
import yaml

from engine import i18n
from engine.analyze import analyze

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
EN = json.loads((ROOT / "locales" / "en.json").read_text(encoding="utf-8"))


def test_every_rule_has_a_sentence():
    rules = yaml.safe_load((ROOT / "config" / "rules.yaml").read_text(encoding="utf-8"))["rules"]
    assert {f"RULE_{r['id']}" for r in rules} <= set(EN["rule"])


def test_every_code_raised_on_the_corpus_has_words():
    shown = ("ID_", "LOOK_", "HOP_")
    for p in FIXTURES.glob("*.eml"):
        for code in analyze(p.read_bytes())["codes"]:
            if code.startswith(shown):
                assert i18n.has(f"flags.{code}"), code


def test_missing_keys_fall_back_safely():
    assert i18n.t("verdict.LIKELY_SCAM.title", "xx") == "Likely a scam"
    assert i18n.t("no.such.key") == "no.such.key"
    assert i18n.t("rule.RULE_INSTITUTION_NAME_WRONG_DOMAIN", name="IRS").startswith("The name says it is IRS")


# A plain Flesch-Kincaid estimate (vowel-group syllables). textstat needs a
# dictionary download that CI cannot rely on, so this is the offline check.
def _syllables(word):
    w = word.lower().strip(".,!?;:'\"()")
    n = len(re.findall(r"[aeiouy]+", w))
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(n, 1)


def _grade(text):
    words = re.findall(r"[A-Za-z][A-Za-z'.-]*", text)
    sentences = max(1, len(re.findall(r"[.!?]+", text)))
    return 0.39 * len(words) / sentences + 11.8 * sum(map(_syllables, words)) / len(words) - 15.59


@pytest.mark.parametrize("key,text", [(f"verdict.{k}.sentence", v["sentence"]) for k, v in EN["verdict"].items()]
                         + [(f"rule.{k}", v) for k, v in EN["rule"].items()]
                         + [(f"note.{k}", v) for k, v in EN["note"].items()])
def test_verdict_text_at_or_below_grade_6(key, text):
    assert _grade(text.replace("{name}", "the bank")) <= 6.0, key


def test_no_english_sentences_in_app_code():
    # Every user-facing sentence lives in locales/; app.py only holds keys.
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    calls = re.findall(r"st\.(?:markdown|success|warning|error|info|caption|subheader|title)\(\s*\"([^\"]+)\"", src)
    assert not [c for c in calls if re.search(r"[A-Za-z]{3,} [A-Za-z]{3,}", c)], calls


@pytest.mark.parametrize("name", ["legit_gmail_001.eml", "phish_wild_008.eml", "phish_wild_009.eml",
                                  "edge_synthetic_truncated_paste_001.eml", "edge_synthetic_punycode_001.eml"])
def test_app_renders_without_errors(name):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.text_area[0].input((FIXTURES / name).read_text(encoding="utf-8")).run()
    at.button[0].click().run()
    assert not at.exception
    banner = (list(at.success) + list(at.warning) + list(at.error))[0].value
    expected = analyze((FIXTURES / name).read_bytes())["verdict"]["tier"]
    assert i18n.t(f"verdict.{expected}.title") in banner


def test_app_asks_for_input_when_empty():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.button[0].click().run()
    assert at.warning[0].value == i18n.t("app.empty_paste")


# --- Spanish (brief, Week 5 / Gate 2) ------------------------------------

ES = json.loads((ROOT / "locales" / "es.json").read_text(encoding="utf-8"))


def _flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        out.update(_flat(v, key + ".") if isinstance(v, dict) else {key: v})
    return out


def test_spanish_has_every_english_string():
    missing = set(_flat(EN)) - set(_flat(ES))
    assert not missing, sorted(missing)


def test_spanish_keeps_the_same_placeholders():
    en, es = _flat(EN), _flat(ES)
    for key, text in en.items():
        assert set(re.findall(r"{(\w+)}", text)) == set(re.findall(r"{(\w+)}", es.get(key, ""))), key


def test_spanish_verdict_labels_follow_the_brief():
    assert ES["verdict"]["CHECKS_OUT"]["title"] == "Parece legítimo"
    assert ES["verdict"]["BE_CAREFUL"]["title"] == "Tenga cuidado"
    assert ES["verdict"]["LIKELY_SCAM"]["title"] == "Probablemente es una estafa"


def test_both_languages_offered():
    assert i18n.available() == ["en", "es"]


@pytest.mark.parametrize("name", ["phish_wild_008.eml", "legit_gmail_001.eml", "phish_wild_011.eml"])
def test_app_renders_in_spanish(name):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.radio[0].set_value("es").run()
    at.text_area[0].input((FIXTURES / name).read_text(encoding="utf-8")).run()
    at.button[0].click().run()
    assert not at.exception
    tier = analyze((FIXTURES / name).read_bytes())["verdict"]["tier"]
    banner = (list(at.success) + list(at.warning) + list(at.error))[0].value
    assert ES["verdict"][tier]["title"] in banner
    page = " ".join(m.value for m in at.markdown)
    if tier != "CHECKS_OUT":
        assert "reportefraude.ftc.gov" in page          # the FTC's own Spanish site


def test_helo_only_entry_is_described_as_a_claim():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.text_area[0].input((FIXTURES / "phish_wild_011.eml").read_text(encoding="utf-8")).run()
    at.button[0].click().run()
    page = " ".join(m.value for m in at.markdown)
    assert "a computer calling itself online.de" in page
