# Decision memo: an in-browser version with stlite

**Decision:** Launch on Streamlit Community Cloud. Do not ship an stlite
build for launch. Keep it as a documented option for partners who need the
email to never leave the reader's device.

**Date:** November 11, 2026 · **Author:** Evelyn Chipangura · **Gate:** 3

## The question

[stlite](https://github.com/whitphx/stlite) runs a Streamlit app entirely
inside the web browser using Pyodide (Python compiled to WebAssembly). With
it, the headers a reader pastes would be checked on their own device and
never sent to any server. The page could be hosted for free as plain files,
for example on GitHub Pages, and would not "go to sleep" between visitors.

Should "Who Really Sent This?" launch as an stlite build instead of, or as
well as, the hosted Streamlit app?

## What I checked

| Question | Finding |
|---|---|
| Can the engine run in the browser? | **Very likely yes.** The engine uses only the Python standard library plus three packages: `confusable-homoglyphs` and `publicsuffix2` (pure Python) and `PyYAML` (included in Pyodide). It makes no network calls (enforced by `tests/test_privacy.py`). |
| Can the app run unchanged? | **Not guaranteed.** The live app uses Streamlit 1.64. The newest stlite release notes I found mention a Streamlit fork based on 1.57, so features added after 1.57 would need checking one by one. |
| Data files | The app reads `locales/`, `config/` and `data/` from disk. stlite can mount these, but each must be listed in the build. |
| First visit | The browser downloads the Python runtime and libraries, typically tens of megabytes, before anything appears. After that, the files are cached. |
| Tests | Our 486 tests run against normal Python and Streamlit. They would not prove the stlite build works; it would need its own browser tests. |

## Options

| | A. Hosted only (chosen) | B. stlite only | C. Both |
|---|---|---|---|
| Privacy | Text passes through Streamlit's servers while checked; nothing stored by the app | **Strongest:** text never leaves the device | Reader chooses |
| First load on an old phone or slow data | **Fast** | Slow, heavy download | Hosted fast, stlite slow |
| Works for our audience (older adults, families, shared library PCs) | **Yes** | Risky: a long blank wait looks broken | Two links may confuse |
| Effort before November 13 | **None** | High (version gap, testing) | Highest |
| Ongoing maintenance | One build | One build, less tested | Two builds |

## Why option A

1. **The audience comes first.** The people this tool is for are most likely
   to use older phones, limited data plans and shared computers. A first
   visit that downloads tens of megabytes and shows a blank page would lose
   many of them before they see a result.
2. **The privacy promise already holds without stlite.** The app stores
   nothing, sends nothing, and looks nothing up, and tests enforce this. The
   privacy page says plainly that the text passes through Streamlit's servers
   while it is checked, and readers can remove their own address first.
3. **Quality.** The hosted app is covered by 486 tests and tested in a real
   browser in both languages. An stlite build on an older Streamlit version
   could not reach that standard by launch.

## When to revisit

Build an stlite version when any of these is true:

- a partner (for example a school district or health clinic) requires that
  email content never reach a third-party server;
- stlite's bundled Streamlit catches up with the features the app uses
  (tabs, file upload, data tables, download button);
- the app needs to work offline, for example in workshops without internet.

## How to try it later (outline)

1. Create `stlite/index.html` that loads `@stlite/browser` and mounts
   `app.py`, `engine/`, `locales/`, `config/` and `data/`, with
   `confusable-homoglyphs` and `publicsuffix2` as requirements.
2. Open it locally and run the three sample emails in both languages.
3. Fix any Streamlit features that the stlite version lacks.
4. Add a browser test (Playwright) that loads the page and checks one green,
   one yellow and one red sample.
5. Publish with GitHub Pages and link it from the README as
   "Private version (runs on your device)".

## Sources

- stlite project: https://github.com/whitphx/stlite
- stlite release notes (`@stlite/browser` changelog): https://app.unpkg.com/@stlite/browser@1.8.1/files/CHANGELOG.md
- Streamlit release notes: https://docs.streamlit.io/develop/quick-reference/release-notes
