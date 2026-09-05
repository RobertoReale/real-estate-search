# Remote Access & Running in the Background

[← Back to README](../README.md)

## Access from Your Phone

The scraper stays on the PC — portals trust residential IPs and block cloud ones
(see *Technical Architecture* in the README) — but the dashboard can be used from
an Android or iOS browser, and installed as an app icon.

Run **`scripts\windows\serve.bat`** instead of `start.bat`. Both serve the
dashboard *and* the API from a single port (8000), but `start.bat` binds
loopback, which only this PC can reach; `serve.bat` binds the Tailscale address
instead, so there is nothing to configure on the phone: open the URL the script
prints, then use the browser's **"Add to home screen"** to get a standalone app
icon.

The layout adapts to the screen: the filter rail becomes a sheet you pull up
and put away, forms fold into two columns, the property grid becomes a single
column, and buttons grow to a thumb-sized
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
Windows, with no console window.

**First, decide whether you need a service at all.** The packaged app (see the
[README](../README.md#windows-without-installing-anything)) already runs with no
console window: it sits in the notification area, and you can put a shortcut to
`RealEstateSearch.exe` in your Startup folder (`Win+R` → `shell:startup`) to have
it come up at every login. For most people that is the whole answer, and it
needs nothing installed.

A **service** buys exactly two things that cannot: it starts at **boot, before
anyone logs in**, and it **restarts itself after a crash**. If you want those,
there is one supported way to get them, below. (Earlier versions also documented
a Startup-folder shortcut and a Task Scheduler task pointing at a
`run-hidden.vbs` helper. Both were the packaged app's job done less well, so the
helper is gone — use the tray app for the at-login case.)

Everything stays on `127.0.0.1` — the API has no password unless you set one, so
it must not be exposed. All the scripts below live in **`scripts\windows\`**.

### Windows Service (NSSM) — the supported service path

It registers the backend as a real service: starts at **boot** (before login),
**auto-restarts on crash**, and logs to `backend/service.log`. One-time setup,
and it needs a small download.

Running it from a source checkout? **Build the dashboard once first** so the
backend serves it on a single port — `scripts\windows\start.bat` does that and
can then be closed, or `cd frontend && npm run build`.

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

> Notes: don't run `start.bat` or the packaged app at the same time (they use
> port 8000 too — stop the service first). After changing the code, rebuild the
> frontend and restart. The automatic DataDome cookie grab runs headless
> (`maybe_auto_refresh`) cleanly in the background right when needed. Any
> **interactive** browser step (solving a CAPTCHA by hand) still works under
> the service: **"Grab a fresh cookie now"** in Settings relaunches the browser
> inside your own desktop session instead of the service's invisible one, so a
> real window opens for you to solve it in. The availability check's own
> **"Show the browser window during the check"** option cannot do this — it
> runs the browser in the service itself, so under the service it is always
> headless no matter the setting (see [Is This Ad Still Online?](availability-check.md)
> for the workaround: run "Grab a fresh cookie now" first).
