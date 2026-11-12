# Who Really Sent This?

**A free, plain-language email checker for the people imposter scams hit hardest.**
Paste an email's headers and get one clear answer, in English or Spanish:

> ✅ **Checks out** · ⚠️ **Be careful** · ⛔ **Likely a scam**

**Try it:** https://who-really-sent-this.streamlit.app

Built by Evelyn Chipangura as a fellowship project with the
[Chicago Education Advocacy Cooperative (ChiEAC)](https://www.linkedin.com/company/chieac/).

---

## Why

Scammers pretend to be banks, schools, the post office and government
offices. Mail apps hide the evidence that would expose them in the email's
headers, which are written for machines. This tool reads those headers and
explains, in sixth-grade language, who really sent the email and why that
matters, with links to report it.

## What it does

- **One clear verdict** with the main reason, written for non-technical readers.
- **Who it's from:** the name and address shown, which organization actually
  vouched for the email, and the first server it came from.
- **The three checks in plain words:** SPF, DKIM and DMARC, including whether
  they line up with the address you see.
- **Imposter detection:** lookalike domains (`paypa1.com`), hidden characters
  (punycode), a bank's name on a free Gmail address, and email addresses
  disguised as display names, checked against a watchlist of 142 commonly
  impersonated institutions.
- **The journey:** each server the email passed through, which ones your own
  mail provider recorded, and forged or odd hops.
- **What to do next:** official reporting links (FTC, FBI IC3, IRS, USPS,
  USCIS), in Spanish where the agency offers it.
- **English and Spanish** with one click, plus a large-text option.
- **Check several emails at once:** upload up to 50 saved emails (.eml or
  .txt) and get them sorted riskiest first, with a CSV summary.
- **Brand settings:** a school, library or credit union can put its own name,
  logo, color and fraud line on its own copy by editing one file
  ([guide](docs/white-label.md)).

## Privacy

Nothing you paste is stored, sent anywhere or looked up on the internet. The
app does not open links or attachments and collects no usage statistics.
Automated tests fail the build if this promise is broken.
Details: [docs/privacy.md](docs/privacy.md).

## How well it works

Tested on **61 real and synthetic emails** (43 legitimate, 8 suspicious, 10
scams) from Gmail, Outlook, Yahoo and iCloud, all anonymized:

| | Result |
|---|---|
| Agreement with the hand-labelled answer | **61 / 61 (100%)** |
| Legitimate emails wrongly called a scam | **0** |
| Automated tests | **486 passing** |

Run the evaluation yourself: `python -m engine evaluate tests/fixtures`

## What it cannot tell you

A pass means the owner of the address sent the email. It does **not** mean
the email is safe: a real account that was hacked will pass, and so will a
scam sent from an ordinary Gmail account. The tool reads only what you paste.

## Run it on your own computer

Requires Python 3.12 or newer.

```bash
git clone https://github.com/echipangura/who-really-sent-this.git
cd who-really-sent-this
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py               # opens http://localhost:8501
```

Command line, without the web page:

```bash
python -m engine summary tests/fixtures         # one line per sample
python -m engine analyze path/to/email.eml      # full JSON report
python -m pytest -q                             # run the tests
```

## How it works

```
headers ─▶ normalize ─▶ trust boundary ─▶ SPF/DKIM/DMARC ─▶ identities ─▶ journey ─▶ lookalike ─▶ rules ─▶ verdict
```

| Step | File | What it does |
|---|---|---|
| Normalize | `engine/normalize.py` | Unfolds and decodes headers, flags damaged input |
| Trust boundary | `engine/trust.py` | Finds the stamp your own mail provider added, so a sender cannot fake it |
| Authentication | `engine/authresults.py` | Reads SPF, DKIM and DMARC from that trusted stamp only |
| Identities | `engine/identities.py` | From, Reply-To, Return-Path, and which organizations vouched |
| Journey | `engine/received.py` | Builds the hop map, finds the entry server and forged hops |
| Lookalike | `engine/lookalike.py` | Homoglyphs, punycode, free-mail and display-name imposters |
| Rules | `engine/rules.py` + `config/rules.yaml` | 15 readable rules turn the findings into a verdict |
| Words | `engine/i18n.py` + `locales/` | Every sentence the reader sees, in English and Spanish |
| Batch | `engine/batch.py` | Checks many saved emails and builds the CSV summary |

The engine returns codes, never sentences, so a new language is a new file in
`locales/` and the rules can be read and changed without touching code.

## Project documents

- [Privacy](docs/privacy.md)
- [Branded copies for partners](docs/white-label.md)
- [Decision memo: in-browser version (stlite)](docs/decision-stlite.md)
- User guides: [English](docs/user-guide-en.md) · [Español](docs/user-guide-es.md)
- [Workshop outline](docs/workshop-outline.md)

## Status

The Spanish translation is a first draft awaiting native-speaker review.
Feedback is welcome through GitHub issues.

## License

[MIT](LICENSE). Free to use, copy and adapt. Branded copies keep the
"Powered by Who Really Sent This?" credit.
