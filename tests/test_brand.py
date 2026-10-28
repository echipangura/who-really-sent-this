"""White-label settings (brief, Section 5.5: "Brand config swaps name, logo,
colors, and links with no code change")."""

from pathlib import Path

import pytest

from engine import brand as B
from engine import i18n

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

CREDIT_UNION = """
organization: {name: Lakeside Community Credit Union, website: "https://example.org"}
app_name: {en: "Is This Email Real? Lakeside CU", es: "¿Es real este correo? Lakeside CU"}
tagline: {en: "A free check from your credit union.", es: ""}
accent_color: "#0B6E4F"
languages: [en]
footer_contact: {en: "Questions? Call us at 555-0100."}
reporting_links:
  all:
    - {label: {en: "Call Lakeside fraud line: 555-0199"}, url: "tel:+15550199"}
  bank:
    - {label: {en: "Lakeside members: freeze your card in the app"}}
"""


@pytest.fixture
def custom_brand(tmp_path, monkeypatch):
    p = tmp_path / "brand.yaml"
    p.write_text(CREDIT_UNION, encoding="utf-8")
    monkeypatch.setattr(B, "BRAND_FILE", p)
    B.load_brand.cache_clear()
    yield B.load_brand()
    B.load_brand.cache_clear()


def test_default_brand_is_chieac():
    b = B.load_brand()
    assert b.org_name == "Chicago Education Advocacy Cooperative"
    assert b.accent_color == "#1F3864" and b.languages == ("en", "es")
    ftc = B.load_brand().links_for("anything")[0]
    assert ftc.link("en") == "https://reportfraud.ftc.gov"
    assert ftc.link("es") == "https://reportefraude.ftc.gov"


def test_category_links_come_before_the_general_ones():
    keys = [x.label_key for x in B.load_brand().links_for("government")]
    assert keys[0] == "todo.report_irs" and "todo.report_ftc" in keys


def test_streamlit_theme_matches_brand_colour():
    toml = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert f'primaryColor = "{B.load_brand().accent_color}"' in toml


def test_missing_or_broken_file_falls_back_safely(tmp_path):
    assert B.load_brand(str(tmp_path / "nope.yaml")).accent_color == B.DEFAULT_ACCENT
    bad = tmp_path / "bad.yaml"
    bad.write_text("organization: [unclosed", encoding="utf-8")
    assert B.load_brand(str(bad)).languages == ("en", "es")


def test_bad_colour_is_ignored(tmp_path):
    p = tmp_path / "b.yaml"
    p.write_text('accent_color: "red; } body {display:none"', encoding="utf-8")
    assert B.load_brand(str(p)).accent_color == B.DEFAULT_ACCENT   # never injected into the page


def test_credit_union_brand_loads(custom_brand):
    assert custom_brand.pick("app_name", "en").startswith("Is This Email Real?")
    assert custom_brand.pick("tagline", "es") == "A free check from your credit union."   # falls back to English
    assert custom_brand.languages == ("en",)
    texts = [x.text("en", i18n.t) for x in custom_brand.links_for("bank")]
    assert texts == ["Lakeside members: freeze your card in the app", "Call Lakeside fraud line: 555-0199"]


def test_app_rebrands_with_no_code_change(custom_brand):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not at.radio                                   # one language: no switch shown
    assert at.title[0].value == "📧 Is This Email Real? Lakeside CU"
    at.text_area[0].input((FIXTURES / "phish_wild_001.eml").read_text(encoding="utf-8")).run()
    at.button[0].click().run()
    assert not at.exception
    page = " ".join(m.value for m in at.markdown)
    assert "[Call Lakeside fraud line: 555-0199](tel:+15550199)" in page
    assert "#0B6E4F" in page                              # the accent colour reached the page
    footer = " ".join(c.value for c in at.caption)
    assert "Lakeside Community Credit Union" in footer and "555-0100" in footer
