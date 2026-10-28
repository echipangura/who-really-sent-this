"""Brand settings for white-label deployments (brief, Section 5.5).

Reads config/brand.yaml: organisation name and link, optional app name,
tagline and logo, accent colour, languages offered, footer contact, and
reporting links by scam category. A school or credit union changes that
one file, never the code.

Missing or empty settings fall back to safe defaults, so a partial or
broken brand file never takes the app down. Holds no user-facing English.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

BRAND_FILE = Path(__file__).resolve().parent.parent / "config" / "brand.yaml"
DEFAULT_ACCENT = "#1F3864"
_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")


@dataclass(frozen=True)
class ReportLink:
    label_key: str | None = None          # a key in locales/, e.g. todo.report_ftc
    label: tuple = ()                      # (("en", "..."), ("es", "...")) when not a key
    url: str | None = None
    url_by_lang: tuple = ()                # (("es", "https://..."),)

    def text(self, lang: str, t) -> str:
        if self.label_key:
            return t(self.label_key, lang)
        labels = dict(self.label)
        return labels.get(lang) or labels.get("en") or ""

    def link(self, lang: str) -> str | None:
        return dict(self.url_by_lang).get(lang) or self.url


@dataclass(frozen=True)
class Brand:
    org_name: str = ""
    org_website: str = ""
    app_name: tuple = ()
    tagline: tuple = ()
    logo: str = ""
    accent_color: str = DEFAULT_ACCENT
    languages: tuple = ("en", "es")
    footer_contact: tuple = ()
    reporting_links: tuple = ()            # ((category, (ReportLink, ...)), ...)

    def pick(self, field_name: str, lang: str) -> str:
        """A per-language text setting, or "" when not set (use the default)."""
        values = dict(getattr(self, field_name))
        return (values.get(lang) or values.get("en") or "").strip()

    def links_for(self, category: str) -> list[ReportLink]:
        table = dict(self.reporting_links)
        return list(table.get(category, ())) + list(table.get("all", ()))


def _per_lang(value) -> tuple:
    if isinstance(value, str):
        return (("en", value),) if value.strip() else ()
    if isinstance(value, dict):
        return tuple((str(k), str(v)) for k, v in value.items() if v and str(v).strip())
    return ()


def _link(entry) -> ReportLink | None:
    if not isinstance(entry, dict):
        return None
    by_lang = tuple((k[4:], v) for k, v in entry.items() if k.startswith("url_") and v)
    link = ReportLink(label_key=entry.get("label_key"), label=_per_lang(entry.get("label")),
                      url=entry.get("url") or None, url_by_lang=by_lang)
    return link if (link.label_key or link.label) else None


@lru_cache(maxsize=4)
def load_brand(path: str | None = None) -> Brand:
    p = Path(path) if path else BRAND_FILE
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (FileNotFoundError, yaml.YAMLError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    org = data.get("organization") or {}
    accent = str(data.get("accent_color") or "")
    langs = tuple(str(x) for x in (data.get("languages") or []) if str(x).strip()) or ("en", "es")
    links = []
    for category, entries in (data.get("reporting_links") or {}).items():
        parsed = tuple(x for x in (_link(e) for e in (entries or [])) if x)
        if parsed:
            links.append((str(category), parsed))
    return Brand(
        org_name=str(org.get("name") or "").strip(),
        org_website=str(org.get("website") or "").strip(),
        app_name=_per_lang(data.get("app_name")),
        tagline=_per_lang(data.get("tagline")),
        logo=str(data.get("logo") or "").strip(),
        accent_color=accent if _HEX.match(accent) else DEFAULT_ACCENT,
        languages=langs,
        footer_contact=_per_lang(data.get("footer_contact")),
        reporting_links=tuple(links),
    )
