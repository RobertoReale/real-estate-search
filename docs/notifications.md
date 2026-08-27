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

## Telegram action buttons

Every property notification (new listing, price change, back on the market)
carries four buttons, so a listing can be triaged from the phone without opening
the dashboard:

| Button | What it does |
|---|---|
| **⭐ Favourite** | Marks the property as a favourite. Tap again to remove it. |
| **👁️ Seen** | Dismisses the message: the buttons disappear and nothing is saved. |
| **🚫 Hide** | Hides the property from the dashboard. Becomes **↩️ Restore**, so a mis-tap is undone with a second tap. |
| **🗺️ Map** | Opens the property's location on OpenStreetMap. Only shown when the property has coordinates. |

Favourite and Hide do exactly what the same-named buttons on a card do, and the
message redraws itself after each tap — so a notification you come back to a day
later still shows the property's real state rather than the state it had when it
was sent.

Turn the buttons off with **Settings → Telegram → Action buttons on
notifications**; the alerts then arrive as plain messages.

**Why no public URL is needed.** Telegram can deliver button presses either by
calling a public web address of yours or by handing them over when asked. This
app asks: the backend polls Telegram over an outgoing connection, exactly like
sending a message. Nothing has to be exposed to the internet, so the buttons work
the same on a loopback-only install as on a Tailscale one — and the dashboard
stays as unreachable from outside as it was before.

Two consequences worth knowing:

- The presses only apply while the backend is running. Ones made while it was off
  are discarded at startup rather than replayed, so a tap from yesterday cannot
  quietly hide something today.
- **Run only one copy of the app against a given bot token.** Two backends
  polling the same bot split the presses between them at random, so roughly half
  the taps appear to do nothing. If you run the app in two places, give each its
  own bot.

## Gmail: use an app password

Gmail rejects your normal password; the email alerts need a 16-character
**app password** (`smtp.gmail.com:587`, username = your Gmail address). Google
only offers app passwords once **2-Step
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
