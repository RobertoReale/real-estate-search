"""The offline sandbox: real HTTP and real SMTP, bound to loopback.

This suite has always been offline, but it was offline by *substitution* — a
fake session object handed to a scraper, a monkeypatched `notify_new_property`.
That proves each part in isolation and says nothing about the seams between
them: the warm-up, the api-next request the scanner really issues, the SMTP
conversation `notifier` really holds. This module closes that gap by serving
the portals and the mail server for real, on 127.0.0.1, so `run_scan` can be
driven end to end without a packet leaving the machine.

Two servers, because the flow has two outbound legs:

- `MockPortalServer` answers the portals' HTTP. The scrapers request exactly
  the absolute URLs named in `PORTAL_URL_ATTRS`; every other URL they touch is
  derived from the search URL the caller passes in, which is already a
  parameter. Adding a portal is one row in that table plus a page renderer.
- `MockSMTPServer` answers the notification's SMTP, and needs no patching at
  all: `smtp_host`/`smtp_port` are settings, so pointing them at loopback is a
  supported configuration and what runs is the real `smtplib` exchange.

There is deliberately **no fake IMAP server**. The inbox import that would have
read one is gone (invariant 12), so nothing in this codebase opens a mailbox
any more; the mail server the flow still needs is the one it *sends* through.
"""

import email
import json
import socket
import socketserver
import threading
import typing
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from app.scrapers import idealista, immobiliare

# The absolute URLs the scrapers actually REQUEST, and the loopback paths the
# sandbox answers them on. Listing URLs (an idealista `/immobile/<id>/` made
# absolute, an api-next `seo.url`) are deliberately absent: those are data a
# scraper writes into a RawListing for the user to click, never something it
# fetches, so leaving them pointing at the real portal is what keeps the
# notification's "Open listing" link honest.
PORTAL_URL_ATTRS: tuple[tuple[typing.Any, str, str], ...] = (
    (immobiliare, "HOMEPAGE", "/immobiliare-home"),
    (immobiliare, "API_GEO", "/api-next/geography/autocomplete/"),
    (immobiliare, "API_LISTINGS", "/api-next/search-list/listings/"),
    (idealista, "HOMEPAGE", "/idealista-home"),
)

_HOMEPAGE_HTML = "<html><body><h1>Case in vendita e in affitto</h1></body></html>"

# What a portal answers for a path it does not have. Shaped like the portals'
# own copy rather than the stdlib's error page, so a mis-routed URL fails in
# the parsers the way a dead slug does on the real site.
_NOT_FOUND_HTML = "<html><body><h1>La pagina che cerchi non esiste</h1></body></html>"


# ---------------------------------------------------------------------------
# One property, rendered per portal
# ---------------------------------------------------------------------------


@dataclass
class Flat:
    """One physical property, as the sandbox will publish it.

    The cross-portal merge is the thing an end-to-end test most needs to be
    able to state, and stating it means two portals describing the *same*
    flat. Holding that description in one object is what stops the two
    renderings from drifting into two different apartments — which is the very
    failure invariant 1 exists to prevent, reproduced in the test data instead
    of in the code.
    """

    ad_id: str
    title: str
    price: int
    rooms: int
    sqm: int
    city: str
    zone: str = ""
    street: str = ""  # "Via Verdi"
    civic: str = ""  # "10"
    latitude: float | None = None
    longitude: float | None = None
    agency: str = ""
    description: str = ""

    @property
    def address(self) -> str:
        return f"{self.street} {self.civic}".strip()


def _italian_thousands(value: int) -> str:
    """250000 -> "250.000". The portals write prices the Italian way, and
    `parse_price` was built against that, dots and all."""
    return f"{value:,}".replace(",", ".")


def immobiliare_api_entry(flat: Flat) -> dict:
    """One `results` entry of the api-next payload — Immobiliare's primary path."""
    return {
        "realEstate": {
            "id": flat.ad_id,
            "title": flat.title,
            "price": {"value": flat.price},
            "properties": [
                {
                    "surface": f"{flat.sqm} m²",
                    "rooms": str(flat.rooms),
                    "location": {
                        "city": flat.city,
                        "macrozone": flat.zone,
                        "address": flat.address,
                        "latitude": flat.latitude,
                        "longitude": flat.longitude,
                    },
                    "description": flat.description,
                }
            ],
            "advertiser": {"agency": {"displayName": flat.agency}},
        },
        "seo": {"url": f"https://www.immobiliare.it/annunci/{flat.ad_id}/"},
    }


def immobiliare_api_page(
    flats: list[Flat], *, max_pages: int = 1, declare_count: bool = True
) -> dict:
    """One api-next page, counted the way the portal counts its own results.

    `declare_count=False` drops that count, which is the only thing separating
    the endpoint's two empty answers: a search that matched nothing says so by
    stating a total of zero, while a soft block is the same HTTP 200 with the
    same empty list and no total at all. A page carrying flats is unaffected —
    the difference exists only when there is nothing to return.
    """
    page: dict[str, typing.Any] = {
        "results": [immobiliare_api_entry(f) for f in flats],
        "maxPages": max_pages,
    }
    if declare_count:
        page["count"] = len(flats)
    return page


def immobiliare_geography(*, comune_id: str = "8042") -> list[dict]:
    """What geography autocomplete answers for a municipality.

    Invariant 7 is why this exists rather than an empty stub: api-next answers
    200 with the whole of Italy when it is called without resolved geographical
    parameters, so the sandbox has to resolve them the way the portal does or
    the test would prove nothing about the request the scraper really makes.
    """
    return [
        {
            "type": immobiliare.GEO_COMUNE,
            "id": comune_id,
            "parents": [
                {"type": immobiliare.GEO_NAZIONE, "id": "IT"},
                {"type": immobiliare.GEO_REGIONE, "id": "12"},
                {"type": immobiliare.GEO_PROVINCIA, "id": "TO"},
            ],
        }
    ]


def idealista_results_page(flats: list[Flat]) -> str:
    """A results page carrying only what the heuristic strategy may read.

    No CSS classes anywhere (invariant 2): the parser finds a card by climbing
    from the `/immobile/<id>/` link until an ancestor holds two of them, so the
    page needs a grid wrapper and **more than one card** for that boundary to
    exist at all. A single-card page lets the climb run to `<html>` and read
    the whole document as one listing — which is the footer bug in miniature,
    and would make this sandbox lie about the parser it is exercising.
    """
    cards = [
        f'<article><a href="/immobile/{f.ad_id}/">{f.title}</a>'
        f"<span>€ {_italian_thousands(f.price)}</span>"
        f"<span>{f.rooms} locali</span><span>{f.sqm} m²</span></article>"
        for f in flats
    ]
    return f"<html><body><main>{''.join(cards)}</main></body></html>"


# ---------------------------------------------------------------------------
# The portal HTTP server
# ---------------------------------------------------------------------------


@dataclass
class Page:
    body: str
    status: int = 200
    content_type: str = "text/html; charset=utf-8"


class _PortalHTTPServer(ThreadingHTTPServer):
    """Carries the page table so the handler can reach it through `self.server`."""

    daemon_threads = True
    pages: dict[str, Page]
    requested: list[str]


class _PortalHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        server = typing.cast(_PortalHTTPServer, self.server)
        server.requested.append(self.path)
        page = server.pages.get(urlparse(self.path).path) or Page(_NOT_FOUND_HTML, status=404)
        body = page.body.encode("utf-8")
        self.send_response(page.status)
        self.send_header("Content-Type", page.content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: typing.Any) -> None:
        """Silence the access log: the suite's output is the report."""


class MockPortalServer:
    """Serves canned portal pages over real HTTP on 127.0.0.1."""

    def __init__(self) -> None:
        httpd = _PortalHTTPServer(("127.0.0.1", 0), _PortalHandler)
        httpd.pages = {}
        httpd.requested = []
        self._httpd = httpd
        self._thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        host, port = typing.cast(tuple[str, int], self._httpd.server_address)
        return f"http://{host}:{port}"

    def url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def serve(
        self,
        path: str,
        body: str,
        *,
        status: int = 200,
        content_type: str = "text/html; charset=utf-8",
    ) -> str:
        """Publish `body` at `path`, replacing whatever was there. Returns the
        absolute URL, so a caller can hand it straight to a scraper."""
        self._httpd.pages[urlparse(path).path] = Page(body, status, content_type)
        return self.url(path)

    def serve_json(self, path: str, payload: typing.Any, *, status: int = 200) -> str:
        return self.serve(
            path,
            json.dumps(payload),
            status=status,
            content_type="application/json",
        )

    @property
    def requested(self) -> list[str]:
        """Every path this server was asked for, in order.

        This is the load-bearing proof that a scrape stayed inside the sandbox:
        a scraper that had gone to the real portal instead would simply be
        missing from it.
        """
        return list(self._httpd.requested)

    def install(self, monkeypatch: typing.Any) -> None:
        """Repoint every portal URL the scrapers request at this server."""
        for module, attr, path in PORTAL_URL_ATTRS:
            monkeypatch.setattr(module, attr, self.url(path))
        self.serve("/immobiliare-home", _HOMEPAGE_HTML)
        self.serve("/idealista-home", _HOMEPAGE_HTML)

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)

    def __enter__(self) -> "MockPortalServer":
        return self

    def __exit__(self, *exc: typing.Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# The notification SMTP server
# ---------------------------------------------------------------------------


class _SMTPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    messages: list[Message]


class _SMTPHandler(socketserver.StreamRequestHandler):
    """Enough SMTP for `notifier.send_email_message`, and nothing more.

    STARTTLS is deliberately not advertised: `notifier` already treats a server
    without it as fine (it catches `SMTPNotSupportedError` and carries on), and
    a sandbox has no business owning a certificate.
    """

    def handle(self) -> None:
        server = typing.cast(_SMTPServer, self.server)
        self.wfile.write(b"220 sandbox.localhost ESMTP\r\n")
        body: list[str] = []
        reading_data = False
        while True:
            raw = self.rfile.readline()
            if not raw:
                return
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if reading_data:
                if line == ".":
                    reading_data = False
                    server.messages.append(email.message_from_string("\n".join(body)))
                    body = []
                    self.wfile.write(b"250 Message accepted\r\n")
                else:
                    # dot-stuffing: a body line starting with "." arrives doubled
                    body.append(line[1:] if line.startswith("..") else line)
                continue
            verb = line.split(" ", 1)[0].upper()
            if verb == "EHLO":
                self.wfile.write(b"250-sandbox.localhost\r\n250 8BITMIME\r\n")
            elif verb == "HELO":
                self.wfile.write(b"250 sandbox.localhost\r\n")
            elif verb in ("MAIL", "RCPT", "RSET", "NOOP"):
                self.wfile.write(b"250 Ok\r\n")
            elif verb == "DATA":
                reading_data = True
                self.wfile.write(b"354 End data with <CR><LF>.<CR><LF>\r\n")
            elif verb == "QUIT":
                self.wfile.write(b"221 Bye\r\n")
                return
            else:
                self.wfile.write(b"502 Command not implemented\r\n")


def message_text(msg: Message) -> str:
    """Subject plus every decoded text part.

    The notification is a multipart/alternative with base64 utf-8 bodies and an
    RFC 2047 subject (it carries emoji), so asserting on the raw message would
    be asserting on the encoding. Flatten it to what a reader would see.
    """
    out = [str(make_header(decode_header(msg.get("Subject", ""))))]
    for part in msg.walk():
        if part.get_content_maintype() != "text":
            continue
        payload = part.get_payload(decode=True)
        if isinstance(payload, bytes):
            out.append(payload.decode(part.get_content_charset() or "utf-8", "replace"))
    return "\n".join(out)


class MockSMTPServer:
    """Captures the notification emails by speaking real SMTP on 127.0.0.1."""

    def __init__(self) -> None:
        server = _SMTPServer(("127.0.0.1", 0), _SMTPHandler)
        server.messages = []
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        return typing.cast(tuple[str, int], self._server.server_address)[1]

    @property
    def messages(self) -> list[Message]:
        return list(self._server.messages)

    def texts(self) -> list[str]:
        return [message_text(m) for m in self.messages]

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def __enter__(self) -> "MockSMTPServer":
        return self

    def __exit__(self, *exc: typing.Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# The offline guarantee
# ---------------------------------------------------------------------------

_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})


def block_external_network(monkeypatch: typing.Any) -> None:
    """Turn any attempt to leave the machine into a failure, not a slow test.

    Honest about which brace holds what: this catches the Python-level paths
    (`smtplib` here, and whatever a future notifier reaches for), but **not**
    curl_cffi, which resolves and connects inside libcurl where no monkeypatch
    can see it. What proves the *scrapers* stayed offline is
    `MockPortalServer.requested` — every page they fetched is in it.
    """
    real_getaddrinfo = socket.getaddrinfo
    real_connect = socket.socket.connect

    def guarded_getaddrinfo(host: typing.Any, *args: typing.Any, **kwargs: typing.Any):
        if host not in _LOOPBACK:
            raise AssertionError(f"offline test tried to resolve {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    def guarded_connect(self: typing.Any, address: typing.Any, *args: typing.Any):
        host = address[0] if isinstance(address, tuple) else address
        if host not in _LOOPBACK:
            raise AssertionError(f"offline test tried to connect to {host!r}")
        return real_connect(self, address, *args)

    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
