"""Turn engine codes into words (brief, Section 5.2 last step).

The engine never contains an English sentence. Every word a user sees lives
in locales/<lang>.json, so a partner can add Polish, Chinese or Arabic by
adding one file. Missing keys fall back to English, then to the key itself,
so a half-translated file never breaks the app.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

LOCALES = Path(__file__).resolve().parent.parent / "locales"
DEFAULT = "en"


@lru_cache(maxsize=16)
def load(lang: str) -> dict:
    p = LOCALES / f"{lang}.json"
    try:
        text = p.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return {}
    return json.loads(text) if text else {}


def available() -> list[str]:
    """Languages with a non-empty locale file, English first."""
    langs = sorted(p.stem for p in LOCALES.glob("*.json") if load(p.stem))
    return sorted(langs, key=lambda x: x != DEFAULT)


def _lookup(table: dict, key: str):
    node = table
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


def has(key: str, lang: str = DEFAULT) -> bool:
    return _lookup(load(lang), key) is not None or _lookup(load(DEFAULT), key) is not None


def t(key: str, lang: str = DEFAULT, **values) -> str:
    """t("verdict.LIKELY_SCAM.title", "es") -> "Probablemente es una estafa"."""
    text = _lookup(load(lang), key) or _lookup(load(DEFAULT), key) or key
    try:
        return text.format(**values) if values else text
    except (KeyError, IndexError, ValueError):
        return text
