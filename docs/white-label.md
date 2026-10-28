# White-label guide: a branded copy in under an hour

This guide is for ChiEAC staff setting up "Who Really Sent This?" for a
partner such as a school, credit union, library or senior centre. You do
not need to write code. Everything is done in a web browser with a GitHub
account, and every change goes in **one file**, `config/brand.yaml`.

| Step | What you do | Time |
| --- | --- | --- |
| 1 | Make the partner's copy of the project | 5 min |
| 2 | Fill in `config/brand.yaml` | 15 min |
| 3 | Add the partner's logo (optional) | 5 min |
| 4 | Set the colour | 2 min |
| 5 | Add local institutions to the watchlist (optional) | 10 min |
| 6 | Put it online | 10 min |
| 7 | Check it | 5 min |

## Before you start

Collect from the partner:

- their name, and the web address the name should link to;
- a logo (PNG, about 400 pixels wide), if they want one;
- their main colour as a hex code, such as `#0B6E4F`;
- which languages to offer (English, Spanish, or both);
- their own fraud line or help desk, such as a phone number or web page;
- any local institutions scammers pretend to be (their own name, the local
  utility, the school district).

## 1. Make the partner's copy

1. Sign in to GitHub and open `https://github.com/echipangura/who-really-sent-this`.
2. Click **Fork** (top right), then **Create fork**. Name it after the
   partner, for example `who-really-sent-this-lakeside`.

All later steps happen in this new copy.

## 2. Fill in `config/brand.yaml`

In your copy, open `config/brand.yaml` and click the pencil icon to edit.

| Setting | What it does | Example |
| --- | --- | --- |
| `organization.name` | Footer: "Brought to you by …" | `Lakeside Community Credit Union` |
| `organization.website` | Link on the name (`""` for none) | `https://lakesidecu.example` |
| `app_name` | A different app name, per language (`""` keeps the standard name) | `{en: "Is This Email Real?", es: "¿Es real este correo?"}` |
| `tagline` | The line under the name (`""` keeps the standard one) | `{en: "A free check from your credit union.", es: ""}` |
| `logo` | Logo above the name (step 3) | `assets/logo.png` |
| `accent_color` | Colour of the main button and links (step 4) | `"#0B6E4F"` |
| `languages` | Languages offered, in order. One language hides the switch | `[en, es]` or `[en]` |
| `footer_contact` | An extra footer line, per language | `{en: "Questions? Call 555-0100.", es: "¿Preguntas? Llame al 555-0100."}` |
| `reporting_links` | Where to report, by the kind of institution faked | see below |

**Reporting links.** Each entry has a label and, if there is one, a link.
`all` is shown on every yellow or red result. The other categories
(`bank`, `school`, `government`, `immigration`, `delivery`, `utility` and
so on) are shown when the email pretends to be that kind of institution.

```yaml
reporting_links:
  all:
    - {label: {en: "Call our fraud line: 555-0199", es: "Llame a nuestra línea de fraude: 555-0199"}, url: "tel:+15550199"}
    - {label_key: todo.report_ftc, url: "https://reportfraud.ftc.gov", url_es: "https://reportefraude.ftc.gov"}
  bank:
    - {label: {en: "Members: freeze your card in our app", es: "Socios: congelen su tarjeta en nuestra app"}}
```

- `label_key` uses a built-in label that is already translated; `label`
  is your own wording, per language.
- `url_es` is an optional Spanish version of the page.
- Phone numbers go in as `tel:+1` followed by the digits, with no spaces.
- Only list **official** pages and numbers. Check each one yourself.

Keep the existing FTC and FBI entries unless the partner asks otherwise.
When you are done, click **Commit changes**.

## 3. Add the logo (optional)

1. In your copy, click **Add file → Upload files**.
2. Type `assets/` before the file name so it goes in an `assets` folder,
   upload the PNG, and commit.
3. In `brand.yaml`, set `logo: assets/logo.png` (use the real file name).

With a logo, the envelope emoji beside the title is hidden.

## 4. Set the colour

Put the same hex code in two places:

1. `accent_color` in `config/brand.yaml` (the main button and links);
2. `primaryColor` in `.streamlit/config.toml` (switches and other controls).

Use a dark colour so white button text stays easy to read. A colour that is
not a valid hex code is ignored and the standard navy is used instead.

## 5. Add local institutions (optional)

The tool warns when an email pretends to be a known institution. To add
the partner's own name and local organisations, edit
`data/impersonated_institutions.csv` and add one line each:

```
Lakeside Community Credit Union,lakesidecu.example,,bank,Lakeside;Lakeside CU,US,
```

The columns are: name, main web domain, other domains (separated by `;`),
category, names a scammer might show (separated by `;`), country, and an
empty last column. Check each domain by typing it into a browser. Avoid
aliases that are everyday words (a person called "Chase", a "Target"
newsletter), because they cause false alarms.

## 6. Put it online

1. Go to **share.streamlit.io** and sign in with GitHub.
2. Click **Create app**, then **Deploy a public app from GitHub**.
3. Repository: your copy. Branch: `main`. Main file path: `app.py`.
4. App URL: a short name, such as `lakeside-email-check`.
5. **Advanced settings:** choose Python 3.14 (or the newest offered).
   Leave Secrets empty: the app needs none.
6. Click **Deploy** and wait two to five minutes.

## 7. Check it

Open the new link and confirm:

- [ ] the partner's name or logo, and colour, appear;
- [ ] the language switch shows the languages you chose;
- [ ] the footer says "Brought to you by" the partner;
- [ ] pasting `tests/fixtures/phish_wild_008.eml` (a fake U.S. Postal
      Service email) gives **Likely a scam** and lists the partner's
      reporting links;
- [ ] each phone number and link opens the right place.

## Making changes later

Edit `config/brand.yaml` in the partner's copy and commit. The live app
updates by itself within a few minutes. If it does not, open the app,
click **Manage app** (bottom right), then **⋮ → Reboot app**.

## Rules for branded copies

- ChiEAC owns the "Who Really Sent This?" name. Keep the "Powered by Who
  Really Sent This?" credit in the footer.
- Do not change the verdict rules (`config/rules.yaml`) or the wording
  in `locales/` for a single partner. Improvements belong in the main
  project, so every copy benefits.
- The privacy promise stays: the app stores nothing, looks nothing up,
  and needs no passwords or keys. Do not add analytics or tracking.
