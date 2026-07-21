# Notifications

[← Back to README](../README.md)

Both channels are configured in **Settings**, with a collapsible step-by-step
guide next to each one:

- **Telegram**: create a bot via **@BotFather**, get your Chat ID via
  **@userinfobot**, paste both, enable, and send a test message.
- **Email**: SMTP settings, enable, and send a test message.

Each test button saves the form before testing, so it always exercises the
values you just typed.

Each search profile can route its own alerts to Telegram only, Email only, both,
or nowhere at all (see *Silencing one search* in [Using the App](using-the-app.md)).

## Gmail: use an app password

Gmail rejects your normal password; both the email alerts and the inbox import
need a 16-character **app password** (`smtp.gmail.com:587`, `imap.gmail.com:993`,
username = your Gmail address). Google only offers app passwords once **2-Step
Verification is on** — until then
[the app passwords page](https://myaccount.google.com/apppasswords) answers *"the
setting you are looking for is not available for your account"*, which is
Google's way of saying "enable 2FA first", not a sign of a problem with this app.
Paste the password as Google shows it: the spaces are stripped on save.

## Scraper health alerts

A broken scraper is silent: it collects no listings, which looks exactly like a
quiet market. When a search profile fails several scans in a row (the portal
blocks the scraper, or its HTML changes), you get an alert on the profile's own
channels, and a matching message once it recovers.

The threshold lives in **Settings → Scraper health alerts** (default: 3
consecutive failures; set it to *Never* to disable). Alerting on a *streak*
rather than a single failure is deliberate — portals hand out occasional
anti-bot blocks that clear by themselves, and an alert that cries wolf gets
ignored. The dashboard also shows the current streak next to a failing
profile's status badge (e.g. `Blocked ×4`).
