# Remote Access & Running in the Background

[← Back to README](../README.md)

## Access from Your Phone

The scraper stays on the PC — portals trust residential IPs and block cloud ones
(see *Technical Architecture* in the README) — but the dashboard can be used from
an Android or iOS browser, and installed as an app icon.

Run **`scripts\windows\serve.bat`** instead of `start.bat`. It builds the frontend and serves the
dashboard *and* the API from a single port (8000), so there is nothing to
configure on the phone: open the URL the script prints, then use the browser's
**"Add to home screen"** to get a standalone app icon.

The layout adapts to the screen: filter bars and forms fold into two columns,
the property grid becomes a single column, and buttons grow to a thumb-sized
target. Wide tables (market velocity) scroll sideways on their own rather than
stretching the page.

**Reaching the PC from outside the house**: install [Tailscale](https://tailscale.com)
on both the PC and the phone and log into the same account. It is free, needs no
port forwarding, and no public IP. `serve.bat` (in `scripts\windows\`) detects the Tailscale address
automatically and binds only to it, so the dashboard is reachable from your own
devices anywhere and from nothing else.

> Note: **By default the API has no password**, so the address is the access
> control:
> - *(default)* Tailscale address — only your own logged-in devices.
> - `scripts\windows\serve.bat lan` — **every device on your Wi-Fi**, guests included. Convenient
>   at home, but do not use it on a network you do not control.
> - Never forward port 8000 on your router.
>
> If you want a wider bind to be safe, set an **API token** (Settings → *API
> access token*). With one set, every device is asked for it once before it can
> see anything; your own browser stays logged in. Empty = the open,
> address-only behavior above.

Scans keep running only while the PC is on. Since listings stay online for days,
one scan a day is usually enough — and Telegram/Email alerts already reach your
phone without any of this. The dashboard is for browsing and triaging.

## Running it 24/7 on Windows (no window to keep open)

Don't have a Raspberry Pi yet? You can make the app run in the background on
Windows, with no console window. Whichever option you pick, **build the
dashboard once first** so the backend serves it on a single port — run
`scripts\windows\serve.bat` once (Ctrl+C after "Building the frontend"), or `cd frontend && npm
run build`. Then open **http://localhost:8000** and bookmark it. Everything
stays on `127.0.0.1` — the API has no password, so it must not be exposed.

All the scripts below live in **`scripts\windows\`**.

Three options, from simplest to most robust:

| Option | What it does | Trade-off |
|---|---|---|
| **A — Start at login (hidden)** | A shortcut to `run-hidden.vbs` in your Startup folder launches the backend, hidden, every time you log in. | Simplest. Runs only after you log in; no auto-restart if it crashes. |
| **B — Task Scheduler (hidden)** | A scheduled task runs `run-hidden.vbs` "At log on", with more control (delay, run even on battery, etc.). | Still tied to login, but more configurable than A. |
| **C — Windows Service (NSSM)** ⭐ | `install-service.bat` registers the backend as a real service: starts at **boot** (before login), **auto-restarts on crash**, logs to `backend/service.log`. | The closest to an always-on appliance. One-time setup, needs a small download. |

**Option A — Start at login.** Press `Win+R`, type `shell:startup`, Enter. In
the folder that opens, right-click → *New → Shortcut*, and point it at
`scripts\windows\run-hidden.vbs`. Done — it launches silently at every
login. (To stop it, delete the shortcut and end `pythonw.exe` in Task Manager.)

**Option B — Task Scheduler.** Open *Task Scheduler* → *Create Task* → trigger
*At log on*, action *Start a program* → `wscript.exe` with argument the full path
to `scripts\windows\run-hidden.vbs`. This gives you options A doesn't (delay after login, "run
whether logged on or not", stop if idle, …).

**Option C — Windows Service (recommended).**
1. Download **NSSM** from <https://nssm.cc/download>, and copy `win64\nssm.exe`
   into `scripts\windows\` (next to `install-service.bat`).
2. Right-click **`scripts\windows\install-service.bat`** → *Run as administrator*. It builds the
   frontend if needed, registers the `RealEstateSearch` service (auto-start,
   auto-restart), and starts it.
3. Open **http://localhost:8000**.

**Using Playwright / Automatic Cookie Grab with NSSM Service:**
When running as a Windows Service at boot (`LocalSystem` account), the service automatically searches for your installed Chromium binaries across user profiles (`C:\Users\<YourUser>\AppData\Local\ms-playwright`) and inside `backend/browser_binaries`.
If Playwright or Chromium is not yet installed:
* Open **http://localhost:8000** → **Settings** and click **⚡ One-Click Install Playwright & Chromium**, *OR*
* Double-click **`scripts\windows\install-playwright.bat`**. It installs Playwright into `backend\.venv`, downloads Chromium, and automatically restarts the `RealEstateSearch` service so it finds Chromium immediately upon boot.

Manage it from an admin terminal: `nssm restart RealEstateSearch` (after
updating the code), `nssm stop RealEstateSearch`, `nssm edit RealEstateSearch`
(GUI). To remove it, run **`uninstall-service.bat`** as administrator — your
database and settings are left untouched.

Double-click helpers for the same actions: **`restart-services.bat`** (restart
after updating the code) and **`stop-service.bat`** (stop it so you can run
`start.bat`/`serve.bat` normally — e.g. to solve a CAPTCHA by hand during the
availability check, since a service has no desktop to show that window on).
Both self-elevate via UAC. Remember to start the service again afterwards
(`restart-services.bat`, or `nssm start RealEstateSearch`).

> Notes for all three: don't run `start.bat` at the same time (both use port
> 8000 — stop the autostart first). After changing the code, rebuild the
> frontend and restart. The automatic DataDome cookie grab runs headless
> (`maybe_auto_refresh`) cleanly in the background right when needed. Any
> **interactive** browser step (solving a CAPTCHA by hand) still works under
> the service: **"Grab a fresh cookie now"** in Settings relaunches the browser
> inside your own desktop session instead of the service's invisible one, so a
> real window opens for you to solve it in. The availability check's own
> **"Show the browser window during the check"** option cannot do this — it
> runs the browser in the service itself, so under the service it is always
> headless no matter the setting (see [Email Inbox Import](email-import.md) for
> the workaround: run "Grab a fresh cookie now" first).
