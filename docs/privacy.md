# Privacy

"Who Really Sent This?" is built so that the email you check stays yours.
The same words appear in the app, in English and Spanish, under
**"Your privacy: what happens to what you paste."**

## What the tool does

- It reads the headers you paste, checks them, and shows the result on the page.
- When you close or refresh the page, your text is gone. The tool keeps no copy.

## What the tool never does

- It never saves what you paste, in a file, a database or a log.
- It never sends your email to anyone, and it does not look anything up on
  the internet (no DNS, WHOIS or reputation lookups).
- It never opens the links or attachments in your email.
- It does not collect usage statistics or track you
  (`gatherUsageStats = false` in `.streamlit/config.toml`).

## Good to know

- The public copy runs on Streamlit Community Cloud. Like any website, your
  text passes through their computers while it is checked. See
  [Streamlit's privacy notice](https://streamlit.io/privacy).
- Headers show your own email address. You can delete the lines that start
  with `To:` and `Delivered-To:` before pasting; the result is the same.
- The tool never needs a password or a code. Never paste one.

## How the promise is checked

`tests/test_privacy.py` runs on every change and fails if:

- the app or engine imports a module that could reach the network or keep a
  record (`requests`, `urllib`, `http`, `socket`, `dns`, `smtplib`,
  `logging`, `sqlite3`, `shelve`);
- usage statistics are switched on;
- removing the `To:` and `Delivered-To:` lines changes the verdict for any
  sample in the corpus;
- the privacy section is missing from the app in either language.

## For branded copies

Partners must keep this promise (see `docs/white-label.md`, "Rules for
branded copies"): no analytics, no tracking, no storage.
