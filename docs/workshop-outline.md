# Workshop: "Is this email real?"

A 60-minute, hands-on session for families, older adults, parents, library
patrons and front-office staff. It can be run in English or Spanish with the
same plan: switch the app to **Español** and use the Spanish handout.

**Goal:** by the end, every participant can (1) spot the main warning signs
of an imposter email, (2) check an email with *Who Really Sent This?*, and
(3) know what to do and where to report it.

## Before the workshop

**Room and equipment**
- A projector or large screen, plus internet.
- Ideally one computer for every 2 participants. The tool works best on a
  computer: phone mail apps usually hide the headers.

**Materials** (all in this repository)
- Printed handouts, one per person: `docs/handout/handout-en.pdf` and
  `docs/handout/handout-es.pdf`.
- Three sample emails for the demo, already anonymized:

  | Sample | File | Expected result |
  |---|---|---|
  | Real bank statement | `tests/fixtures/legit_gmail_001.eml` | ✅ Checks out |
  | School fee with a Gmail reply address | `tests/fixtures/edge_synthetic_reply_to_hijack_001.eml` | ⚠️ Be careful |
  | Fake U.S. Postal Service delivery notice | `tests/fixtures/phish_wild_008.eml` | ⛔ Likely a scam |

  Save them as .txt files on each workshop computer so participants can open
  and copy them.
- Feedback forms (Appendix B), one per person.

**Facilitator check (15 minutes before)**
- Open https://who-really-sent-this.streamlit.app. If it shows "This app has
  gone to sleep", click the button to wake it and wait a minute.
- Paste each sample and confirm the expected result.
- Turn on **Large text** in the side menu for the projector.

## Plan (60 minutes)

| Time | Section | What happens |
|---|---|---|
| 0–5 | **Welcome** | Introductions. Ask: "Who has received an email that made you worry?" Choose the language for the session. |
| 5–15 | **How imposter emails work** | Show that the name you see ("U.S. Postal Service") is typed by the sender and can be anything. Only the hidden headers show who really sent it. Walk through the 5 warning signs on the handout. |
| 15–25 | **Live demo** | Paste the three samples one at a time. For each, read the verdict aloud, then scroll to **Why** and **Who it's from**. Ask the room to guess first. |
| 25–40 | **Hands-on** | In pairs, participants open a sample file, copy everything, paste it into the app and read the result to each other. Faster pairs try **Check several emails** with all three files. Walk around and help. |
| 40–48 | **What to do next** | On the red result, go through **What to do next**: do not click, go to the real website yourself, call a number you trust, report it. Show the FTC site (reportfraud.ftc.gov / reportefraude.ftc.gov). |
| 48–53 | **What the tool cannot tell you** | A ✅ means the owner of the address sent it, not that it is safe. A hacked account still passes. Golden rule: **any email asking for money, passwords or codes gets checked another way.** |
| 53–60 | **Questions and feedback** | Answer questions. Participants fill in the feedback form (Appendix B). Point to the website and QR code on the handout. |

## Teaching tips

- **Use the samples, not personal emails, on the projector.** Headers contain
  real email addresses. If a participant wants to check their own email, help
  them on their own screen, not the shared one.
- Remind people that the tool **never needs a password**. If anything asks
  for one, it is not this tool.
- Keep the words simple: say "the hidden lines of the email" before
  "headers", and "the email's ID checks" before "SPF, DKIM and DMARC".
- Some people only use email on a phone. Show them how to open Gmail or
  Outlook in a web browser on a computer at the library.

## Appendix A: The 5 warning signs (also on the handout)

1. **Urgency or fear:** "Your account will be closed today."
2. **A request for money, gift cards, passwords or codes.**
3. **The name and the address do not match:** "Chase Bank" from
   `chase-alerts@gmail.com`.
4. **A look-alike address:** `paypa1.com`, `amaz0n-support.net`.
5. **"Reply to" goes somewhere else:** your reply would go to a different
   address than the one that sent it.

## Appendix B: Feedback form

Name (optional): ______________ Language used: English / Español

1. Was the tool easy to use? **1** (very hard) – **5** (very easy)
2. Did you understand the result? Yes / Partly / No
3. Would you use it again, or tell a friend? Yes / Maybe / No
4. What was confusing, or what would you change? ______________________

Facilitators: please send the completed forms (or a summary) to the project
team so the tool keeps improving.

## Appendix C: For partner organizations

If your organization runs its own branded copy of the tool (see
`docs/white-label.md`), use your copy's web address and add your own fraud
line to the handout.
