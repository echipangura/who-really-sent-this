"""Who Really Sent This? Streamlit interface (brief, Section 3.1).

Run locally:   streamlit run app.py

Everything shown comes from engine.analyze() (codes and values) turned into
words by engine.i18n (locales/<lang>.json). This file holds no user-facing
English of its own, and nothing the user pastes is stored or logged: the
text lives only in this browser session's memory while the page is open.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from engine import i18n
from engine.analyze import analyze

# Official help pages for finding headers (checked October 2026).
HELP_LINKS = {
    "Gmail": "https://support.google.com/mail/answer/29436",
    "Outlook": "https://support.microsoft.com/en-us/topic/cd039382-dc6e-4264-ac74-c048563d212c",
    "Yahoo": "https://help.yahoo.com/kb/SLN28478.html",
}
# Where to report, by the category of institution being impersonated.
REPORT_LINKS = {
    "all": [("todo.report_ftc", "https://reportfraud.ftc.gov"),
            ("todo.report_ic3", "https://www.ic3.gov")],
    "government": [("todo.report_irs", "https://www.irs.gov/privacy-disclosure/report-phishing")],
    "immigration": [("todo.report_uscis", "https://www.uscis.gov/avoid-scams/report-scams")],
    "delivery": [("todo.report_uspis", "https://www.uspis.gov/report/")],
}
PROVIDER_NAMES = {"gmail": "Gmail", "outlook": "Outlook", "yahoo": "Yahoo Mail", "icloud": "iCloud Mail"}
BANNER = {"CHECKS_OUT": ("✅", st.success), "BE_CAREFUL": ("⚠️", st.warning), "LIKELY_SCAM": ("⛔", st.error)}
# Shown, but as "good to know" rather than red flags: on their own they are
# normal (a person's Gmail, a mail service's bounce address).
INFO_ONLY = {"ID_FREEMAIL_FROM", "ID_RETURN_PATH_MISMATCH"}
SHOWN_FLAGS = ("ID_", "LOOK_", "HOP_", "NORM_POSSIBLY", "NORM_NO_HEADERS", "NORM_MISSING_AUTH",
               "NORM_INPUT_TOO_LARGE", "TRUST_NO", "TRUST_GENERIC")


def duration(seconds: int | None, lang: str) -> str:
    if seconds is None:
        return ""
    if seconds < 0:
        return i18n.t("time.negative", lang, delay=duration(-seconds, lang))
    for unit, size in (("days", 86400), ("hours", 3600), ("minutes", 60)):
        if seconds >= size:
            return i18n.t(f"time.{unit}", lang, n=round(seconds / size, 1 if unit == "days" else 0))
    return i18n.t("time.seconds", lang, n=seconds)


def result_word(result: str | None, lang: str) -> str:
    key = f"auth.result_{(result or 'missing').lower()}"
    return i18n.t(key, lang) if i18n.has(key, lang) else (result or i18n.t("auth.result_missing", lang))


def short_time(iso: str | None) -> str:
    if not iso:
        return ""
    return datetime.fromisoformat(iso).strftime("%b %d, %H:%M:%S UTC")


def render(report: dict, lang: str) -> None:
    T = lambda key, **kw: i18n.t(key, lang, **kw)  # noqa: E731
    v, ids, imp = report["verdict"], report["identities"], report["impersonation"]
    claimed = (imp or {}).get("claimed") or {}
    name = claimed.get("name", "")

    # 1. Verdict banner: colour always paired with an icon and words.
    icon, box = BANNER[v["tier"]]
    first = f"\n\n{T('rule.' + v['reasons'][0], name=name)}" if v["reasons"] else ""
    box(f"### {icon} {T(f'verdict.{v['tier']}.title')}\n\n{T(f'verdict.{v['tier']}.sentence')}{first}")
    for note in v["notes"]:
        st.info(T(f"note.{note}"))

    # 2. Who it says it is from, and where it came from.
    st.subheader(T("who.title"))
    entry = next((h for h in report["journey"]["hops"] if h["entry"]), None)
    vouched = sorted(set(ids["dkim_pass_orgs"] + ([ids["spf_org"]] if ids["spf_aligned"] or
                                                   report["auth"]["spf"]["result"] == "pass" else [])) - {None})
    rows = [
        (T("who.shown_name"), ids["from_display"] or T("who.unknown")),
        (T("who.shown_address"), ids["from_address"] or T("who.unknown")),
        (T("who.vouched"), ", ".join(vouched) or T("who.vouched_none")),
        (T("who.first_server"), " ".join(x for x in ((entry or {}).get("from_ptr") or (entry or {}).get("from_host"),
                                                      f"[{entry['from_ip']}]" if entry and entry.get("from_ip") else None) if x)
         or T("who.unknown")),
    ]
    st.markdown("\n".join(f"- **{k}:** `{val}`" for k, val in rows))
    if claimed and "LOOK_DISPLAY_NAME_SPOOF" in report["codes"]:
        st.markdown(T("who.claims", name=name, domains=", ".join(claimed["domains"])))
    if imp.get("imitated_domain"):
        st.markdown(T("who.lookalike", shown=ids["from_address"].split("@")[-1], real=imp["imitated_domain"]))
    if imp.get("decoded_domain"):
        st.markdown(T("who.punycode", decoded=imp["decoded_domain"]))

    # 3. Authentication in plain language.
    st.subheader(T("auth.title"))
    a = report["auth"]
    provider = PROVIDER_NAMES.get(report["trust"]["provider"], T("auth.provider_generic"))
    st.caption(T("auth.your_provider", provider=provider))
    spf_dom = a["spf"]["domain"] or ids["from_org"] or "?"
    dkim = a["dkim"]
    dkim_result = "pass" if any(d["result"] == "pass" for d in dkim) else (dkim[0]["result"] if dkim else None)
    from_dom = a["dmarc"]["header_from"] or ids["from_org"] or "?"
    policy = (a["dmarc"]["policy"] or "").lower()
    lines = [
        (T("auth.spf_name"), T("auth.spf_what", domain=spf_dom), result_word(a["spf"]["result"], lang)),
        (T("auth.dkim_name"), T("auth.dkim_what"), result_word(dkim_result, lang)),
        (T("auth.dmarc_name"), T("auth.dmarc_what", domain=from_dom), result_word(a["dmarc"]["result"], lang)
         + (f" · {T(f'auth.policy_{policy}')}" if policy in ("reject", "quarantine", "none") else "")),
    ]
    for label, question, answer in lines:
        st.markdown(f"**{label}** · {question}  \n→ **{answer}**")
    st.markdown(("✔️ " + T("auth.aligned_yes")) if ids["aligned"] else ("✖️ " + T("auth.aligned_no")))
    if ids["aligned"] and v["tier"] != "CHECKS_OUT":
        st.caption(T("auth.aligned_but"))

    # 4. Red flags.
    st.subheader(T("flags.title"))
    flags = [c for c in report["codes"] if c.startswith(SHOWN_FLAGS) and i18n.has(f"flags.{c}", lang)]
    say = lambda c: T(f"flags.{c}", reply_to=", ".join(ids["reply_to"]))  # noqa: E731
    red = [c for c in dict.fromkeys(flags) if c not in INFO_ONLY]
    info = [c for c in dict.fromkeys(flags) if c in INFO_ONLY
            and not (c == "ID_FREEMAIL_FROM" and "LOOK_FREEMAIL_INSTITUTION" in flags)]
    st.markdown("\n".join(f"- 🚩 {say(c)}" for c in red) if red else T("flags.none"))
    if info:
        st.markdown(f"**{T('flags.info_title')}**\n" + "\n".join(f"- ℹ️ {say(c)}" for c in info))

    # 5. The journey: a numbered path, oldest first.
    st.subheader(T("journey.title"))
    hops = report["journey"]["hops"]
    if not hops:
        st.markdown(T("journey.none"))
    else:
        st.caption(T("journey.intro"))
        out = []
        for h in hops:
            src = h["from_ptr"] or h["from_host"] or h["from_ip"] or (
                T("journey.inside") if h["trusted"] else T("journey.unknown_host"))
            line = f"**{T('journey.step', n=h['number'])}:** `{T('journey.from_to', **{'from': src, 'to': h['by_host'] or T('journey.unknown_host')})}`"
            if h["timestamp"]:
                line += f" · {T('journey.at', time=short_time(h['timestamp']))}"
            if h["delay_seconds"] is not None:
                line += f" · {T('journey.after', delay=duration(h['delay_seconds'], lang))}"
            tag = T("journey.entry") if h["entry"] else T("journey.trusted") if h["trusted"] else T("journey.claimed")
            line += f"  \n{'📥' if h['entry'] else '🔒' if h['trusted'] else '❔'} _{tag}_"
            out.append(line)
        st.markdown("\n\n".join(out))
        if report["journey"]["total_seconds"] is not None:
            st.caption(T("journey.total", delay=duration(report["journey"]["total_seconds"], lang)))

    # 6. Why this answer.
    st.subheader(T("why.title"))
    if v["reasons"]:
        st.markdown("\n".join(f"- {T('rule.' + r, name=name)}" for r in v["reasons"]))
    else:
        st.markdown(T("why.none"))

    # 7. What to do next, with reporting links chosen by category.
    st.subheader(T("todo.title"))
    st.markdown("\n".join(f"- {T(k)}" for k in ("todo.dont_click", "todo.go_direct", "todo.never_share",
                                                 "todo.ask")))
    if v["tier"] != "CHECKS_OUT":
        st.markdown(f"**{T('todo.report_title')}**")
        st.markdown(T("todo.report_in_app"))
        cat = claimed.get("category", "")
        links = REPORT_LINKS.get(cat, []) + REPORT_LINKS["all"]
        items = [f"- [{T(k)}]({url})" for k, url in links]
        if cat == "bank":
            items.append(f"- {T('todo.report_bank')}")
        if cat == "school":
            items.append(f"- {T('todo.report_school')}")
        st.markdown("\n".join(items))

    # 8. What this tool cannot tell you.
    st.subheader(T("limits.title"))
    st.markdown(T("limits.text"))


def main() -> None:
    st.set_page_config(page_title=i18n.t("app.title"), page_icon="📧", layout="centered")
    langs = i18n.available()
    names = {"en": "English", "es": "Español"}
    lang = st.sidebar.selectbox("🌐", langs, format_func=lambda x: names.get(x, x),
                                label_visibility="collapsed") if len(langs) > 1 else "en"
    T = lambda key, **kw: i18n.t(key, lang, **kw)  # noqa: E731

    if st.sidebar.toggle(T("app.large_text")):
        st.markdown("<style>html, body, [class*='st-'] {font-size: 1.25rem !important;}</style>",
                    unsafe_allow_html=True)

    st.title(f"📧 {T('app.title')}")
    st.markdown(T("app.tagline"))

    with st.expander(T("guide.title")):
        st.markdown(T("guide.intro"))
        for key in ("gmail", "outlook", "outlook_desktop", "yahoo", "apple"):
            st.markdown(f"- {T(f'guide.{key}')}")
        st.markdown(" · ".join(f"[{T('guide.help_link', provider=p)}]({u})" for p, u in HELP_LINKS.items()))

    raw = st.text_area(T("app.paste_label"), help=T("app.paste_help"), height=220)
    st.caption("🔒 " + T("app.privacy"))
    if st.button(T("app.check_button"), type="primary"):
        if not raw.strip():
            st.warning(T("app.empty_paste"))
        else:
            st.divider()
            render(analyze(raw), lang)


main()
