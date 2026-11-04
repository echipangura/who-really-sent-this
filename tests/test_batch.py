"""Batch mode: check several saved emails at once (brief, Gate 3)."""

import csv
import io
from pathlib import Path

import pytest

from engine import batch, i18n
from engine.analyze import analyze

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = sorted((ROOT / "tests" / "fixtures").glob("*.eml"))


def _files():
    return [(p.name, p.read_bytes()) for p in FIXTURES]


def test_same_verdicts_as_one_at_a_time():
    rows = {r.name: r for r in batch.check_many(_files()[:batch.MAX_FILES])}
    for p in FIXTURES[:batch.MAX_FILES]:
        assert rows[p.name].tier == analyze(p.read_bytes())["verdict"]["tier"]


def test_riskiest_first():
    order = [batch.RISK_ORDER[r.tier] for r in batch.check_many(_files())]
    assert order == sorted(order)


def test_counts_add_up():
    rows = batch.check_many(_files()[:batch.MAX_FILES])
    c = batch.counts(rows)
    assert sum(c.values()) == len(rows) == min(len(FIXTURES), batch.MAX_FILES)
    assert c["LIKELY_SCAM"] >= 1 and c["CHECKS_OUT"] >= 1


def test_file_limit():
    many = _files() * 2
    assert len(many) > batch.MAX_FILES
    assert len(batch.check_many(many)) == batch.MAX_FILES


def test_junk_file_does_not_stop_the_others():
    rows = batch.check_many([("photo.txt", b"\x89PNG\r\n\x1a\n\x00\xff\xfe"), _files()[0]])
    assert len(rows) == 2


@pytest.mark.parametrize("lang", ["en", "es"])
def test_csv_summary_in_each_language(lang):
    t = lambda key, **kw: i18n.t(key, lang, **kw)  # noqa: E731
    rows = batch.check_many(_files()[:5])
    table = list(csv.reader(io.StringIO(batch.to_csv(rows, t))))
    assert table[0][0] == t("batch.col_file")
    assert len(table) == 6
    titles = {i18n.t(f"verdict.{x}.title", lang) for x in batch.RISK_ORDER}
    assert all(row[1] in titles for row in table[1:])


def test_csv_blocks_spreadsheet_formulas():
    row = batch.BatchRow("x.eml", "LIKELY_SCAM", None, "", '=HYPERLINK("http://evil")', "a@b.com", None)
    text = batch.to_csv([row], lambda key, **kw: i18n.t(key, "en", **kw))
    assert "'=HYPERLINK" in text


def test_batch_tab_shows_in_both_languages():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert [t.label for t in at.tabs] == [i18n.t("batch.tab_one", "en"), i18n.t("batch.tab_many", "en")]
    at.radio[0].set_value("es").run()
    assert [t.label for t in at.tabs] == [i18n.t("batch.tab_one", "es"), i18n.t("batch.tab_many", "es")]
    assert not at.exception
