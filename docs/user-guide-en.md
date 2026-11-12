# Who Really Sent This? User guide

**Website:** https://who-really-sent-this.streamlit.app
**Cost:** free · **Languages:** English and Spanish

## What is it?

Scammers send emails that pretend to come from your bank, your school, the
post office or the government. This tool checks the hidden lines of an email,
called **headers**, and tells you who really sent it.

Use it when an email:

- asks you to pay, click a link, log in or call a number;
- says your account is locked or a package is waiting;
- looks real, but something feels wrong.

## How to check an email (4 steps)

### Step 1. Open the website

Go to **who-really-sent-this.streamlit.app**. To use Spanish, click
**Español** at the top. For bigger letters, turn on **Large text** in the
side menu.

### Step 2. Copy the email's headers

Open the email in your mail app, then:

| Mail app | What to click |
|---|---|
| **Gmail** | Three dots (⋮) next to Reply → **Show original** → **Copy to clipboard** |
| **Outlook.com** | Three dots (…) → **View** → **View message source** → select all and copy |
| **Outlook on a computer** | **File** → **Properties** → copy the box called **Internet headers** |
| **Yahoo Mail** | Three dots (…) → **View raw message** → select all and copy |
| **Apple Mail (Mac)** | **View** → **Message** → **Raw Source** → select all and copy |

To select all, press **Ctrl + A** (Windows) or **Cmd + A** (Mac). To copy,
press **Ctrl + C** or **Cmd + C**.

> 💡 It is fine to copy the whole message. The tool only reads the headers.

### Step 3. Paste and check

Click in the big box, press **Ctrl + V** (or **Cmd + V**) to paste, then click
**Check this email**.

### Step 4. Read the answer

| You see | What it means | What to do |
|---|---|---|
| ✅ **Checks out** | The email really came from the address it shows. | It is probably fine. But if it asks for money or passwords, still check another way. |
| ⚠️ **Be careful** | Something is not right. | Do not act on the email yet. Check with the sender in another way. |
| ⛔ **Likely a scam** | The email is not from who it says. | Do not click, reply or pay. Report it and delete it. |

Under the answer, the page explains **why**, shows **who it is really from**,
and lists **what to do next**.

## If it is a scam

1. **Do not** click links or call phone numbers in the email.
2. Go to the real website yourself. Type the address.
3. Never send passwords, codes or bank details by email.
4. Not sure? Call the company on a number you already trust, like the one on
   your card or bill.
5. Report it:
   - in your mail app (Gmail: **Report phishing**; Outlook: **Report** →
     **Report phishing**; Yahoo: **Spam**; Apple Mail: **Move to Junk**);
   - to the Federal Trade Commission: **reportfraud.ftc.gov**;
   - the result page also shows the right place for fake bank, school, tax,
     immigration and postal emails.

## Checking many emails at once

Good for a school office, library or front desk.

1. Save each email as a file:
   - **Gmail:** open the email → ⋮ → **Download message**
   - **Outlook on the web:** open the email → … → **Save as** or **Download**
   - **Apple Mail:** **File** → **Save As** → **Raw Message Source**
2. On the website, click the **Check several emails** tab.
3. Add up to 50 files and click **Check these emails**.
4. The riskiest emails are listed first. Click **Download this summary (CSV)**
   to keep a list.

## Your privacy

- Nothing you paste is saved or sent anywhere. When you close the page, it is
  gone.
- The tool does not open links or attachments, and it does not track you.
- Your own email address is in the headers. If you like, delete the lines
  that start with **To:** and **Delivered-To:** before you paste. The check
  still works.
- **Never** paste a password or a code. The tool never needs them.

## What this tool cannot tell you

✅ **Checks out** means the owner of the address sent the email. It does
**not** mean the email is safe:

- if a real account was hacked, its emails will still pass;
- a scammer using an ordinary Gmail account will also pass.

So if any email asks for money, passwords or codes, check with the person or
company another way, even when it checks out.

## Questions and feedback

Found a problem or have an idea? Visit
https://github.com/echipangura/who-really-sent-this and open an issue, or ask
the organization that shared this tool with you.
