"""Offline export of a property shortlist as CSV, Markdown, a self-contained
HTML dossier, or a print-ready one that the browser saves as PDF.

The point is sharing without exposing anything: the local dashboard is
unauthenticated and the SQLite file holds the whole history, so neither can be
handed to a partner or an agent. A dossier is a single file — no server, no
network (bar the listing thumbnails, which are remote portal URLs) — that can be
sent over chat or email and opened anywhere.

It renders whatever the caller selected under the current dashboard filters,
including the transient Deal/Match/market annotations when they were computed,
so the file mirrors exactly what the user was looking at.
"""

import csv
import html as html_lib
import io
from datetime import UTC, datetime

from ..models import Property


def _fmt_price(value: float | None, contract: str = "sale") -> str:
    if not value:
        return "—"
    formatted = f"{value:,.0f} €".replace(",", ".")
    return f"{formatted}/month" if contract == "rent" else formatted


def _sqm_price(p: Property) -> int | None:
    if p.current_min_price and p.sqm:
        return round(p.current_min_price / p.sqm)
    return None


def _fmt_date(value: datetime | None) -> str:
    # SQLite hands back naive datetimes; only the date is printed, so there is
    # nothing to reattach a timezone for here.
    return f"{value:%Y-%m-%d}" if value else "—"


def _primary_url(p: Property) -> str:
    return p.listings[0].url if p.listings else ""


def _gallery_urls(p: Property, limit: int = 6) -> list[str]:
    """Every distinct photo the property has, cover first.

    A merged property carries one ad per agency and each ad brings its own
    photo, so a merge is exactly what turns a single thumbnail into a real
    gallery — the same flat shot from three angles is what a viewing sheet
    wants. Capped because the source is a portal CDN and a printed page is not
    a photo album.
    """
    urls: list[str] = []
    for candidate in (p.image_url, *(l.image_url for l in p.listings)):
        if candidate and candidate not in urls:
            urls.append(candidate)
        if len(urls) >= limit:
            break
    return urls


def _history_rows(p: Property) -> list[tuple[str, str, str]]:
    """The asking-price timeline as (date, price, change), oldest first.

    Neither field says it alone: `first_price` is what the property was first
    seen at, and `price_history` holds one row per change of the *minimum*
    price (invariant 6). The two together are the timeline the printed report
    needs, and the drop percentage is what a negotiation actually leans on.
    """
    rows: list[tuple[str, str, str]] = []
    if p.first_price:
        rows.append(
            (_fmt_date(p.first_seen_at), _fmt_price(p.first_price, p.contract), "first seen")
        )
    for h in p.price_history:
        change = "—"
        if h.old_price:
            change = f"{(h.new_price - h.old_price) / h.old_price * 100:+.1f}%"
        rows.append((_fmt_date(h.changed_at), _fmt_price(h.new_price, p.contract), change))
    return rows


def _sources(p: Property) -> str:
    return " | ".join(l.url for l in p.listings)


# Scraped fields are untrusted in every export format. In Markdown, many
# renderers (VS Code preview, Obsidian) pass raw HTML through, so a title
# containing "<img onerror=…>" becomes live markup the moment the dossier is
# opened; escaping like the HTML export already does closes that. In CSV,
# a leading =, +, - or @ makes Excel execute the cell as a formula
# (CSV/formula injection); the conventional defence is a quote prefix.


def _md(value: str) -> str:
    return html_lib.escape(value or "")


def _csv_text(value: str) -> str:
    s = value or ""
    return f"'{s}" if s[:1] in ("=", "+", "-", "@") else s


def properties_to_csv(props: list[Property]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Title",
            "City",
            "Zone",
            "Address",
            "Contract",
            "Price",
            "Sqm",
            "Rooms",
            "Floor",
            "EUR/sqm",
            "Status",
            "Deal score",
            "Match score",
            "Favorite",
            "First seen",
            "URLs",
        ]
    )
    for p in props:
        writer.writerow(
            [
                _csv_text(p.title),
                _csv_text(p.city),
                _csv_text(p.zone),
                _csv_text(p.address),
                p.contract,
                p.current_min_price if p.current_min_price is not None else "",
                p.sqm if p.sqm is not None else "",
                p.rooms if p.rooms is not None else "",
                _csv_text(p.floor),
                _sqm_price(p) or "",
                p.status,
                getattr(p, "deal_score", None)
                if getattr(p, "deal_score", None) is not None
                else "",
                getattr(p, "match_score", None)
                if getattr(p, "match_score", None) is not None
                else "",
                "yes" if p.is_favorite else "no",
                p.first_seen_at.date().isoformat() if p.first_seen_at else "",
                _sources(p),
            ]
        )
    return buffer.getvalue()


def properties_to_markdown(props: list[Property], title: str) -> str:
    lines = [
        f"# {title}",
        "",
        f"_{len(props)} properties · generated {datetime.now(UTC):%Y-%m-%d %H:%M UTC}_",
        "",
    ]
    for p in props:
        sqm_price = _sqm_price(p)
        lines.append(f"## {_md(p.title) or 'Untitled'}")
        location = " · ".join(_md(x) for x in (p.city, p.zone, p.address) if x)
        lines.append(f"- **Location:** {location or '—'}")
        price = _fmt_price(p.current_min_price, p.contract)
        if sqm_price:
            price += f" ({sqm_price:,} €/sqm)".replace(",", ".")
        lines.append(f"- **Price:** {price}")
        facts = []
        if p.rooms:
            facts.append(f"{p.rooms} rooms")
        if p.sqm:
            facts.append(f"{p.sqm:.0f} sqm")
        if p.floor:
            facts.append(f"floor {_md(p.floor)}")
        if facts:
            lines.append(f"- **Details:** {', '.join(facts)}")
        deal = getattr(p, "deal_score", None)
        if deal is not None and getattr(p, "deal_label", None) != "fair":
            lines.append(f"- **Deal score:** {deal:+d}% ({getattr(p, 'deal_label', '')})")
        match = getattr(p, "match_score", None)
        if match is not None:
            lines.append(f"- **Match:** {match}%")
        if len(p.price_history) > 0:
            hist = ", ".join(
                f"{_fmt_price(h.old_price, p.contract)}→{_fmt_price(h.new_price, p.contract)}"
                for h in p.price_history
            )
            lines.append(f"- **Price history:** {hist}")
        for l in p.listings:
            agency = f" — {_md(l.agency)}" if l.agency else ""
            lines.append(f"- **{_md(l.portal)}**{agency}: {l.url}")
        lines.append("")
    return "\n".join(lines)


# Inlined so the dossier is a single self-contained file (strict offline).
_HTML_STYLE = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  margin: 0; padding: 24px; background: #f8fafc; color: #0f172a; }
h1 { font-size: 20px; margin: 0 0 4px; }
.meta { color: #64748b; font-size: 13px; margin-bottom: 20px; }
.grid { display: grid; gap: 16px;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px;
  overflow: hidden; }
.card img { width: 100%; height: 160px; object-fit: cover; background: #e2e8f0; }
.body { padding: 12px 14px; }
.price { font-size: 18px; font-weight: 700; }
.sqm { color: #64748b; font-size: 12px; margin-left: 6px; }
.title { font-size: 14px; font-weight: 600; margin: 6px 0 2px; }
.loc { color: #64748b; font-size: 12px; }
.facts { font-size: 12px; margin-top: 6px; color: #334155; }
.badges { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
.badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 8px; }
.good { background: #d1fae5; color: #065f46; }
.warn { background: #fef3c7; color: #92400e; }
.muted { background: #e2e8f0; color: #475569; }
.hist { font-size: 11px; color: #475569; margin-top: 6px; }
.links { margin-top: 8px; font-size: 12px; }
.links a { color: #2563eb; text-decoration: none; margin-right: 10px; }
@media (prefers-color-scheme: dark) {
  body { background: #0f172a; color: #e2e8f0; }
  .card { background: #1e293b; border-color: #334155; }
  .title { color: #f1f5f9; } .facts { color: #cbd5e1; }
}
"""


def _card_html(p: Property) -> str:
    esc = html_lib.escape
    sqm_price = _sqm_price(p)
    img = f'<img src="{esc(p.image_url)}" alt="" loading="lazy">' if p.image_url else ""
    badges = []
    deal = getattr(p, "deal_score", None)
    if deal is not None and getattr(p, "deal_label", None) != "fair":
        cls = "good" if deal > 0 else "warn"
        badges.append(
            f'<span class="badge {cls}">🎯 {abs(deal)}% '
            f"{'below' if deal > 0 else 'above'} market</span>"
        )
    match = getattr(p, "match_score", None)
    if match is not None:
        badges.append(f'<span class="badge muted">🎯 {match}% match</span>')
    if p.contract == "rent":
        badges.append('<span class="badge muted">🔑 rent</span>')
    facts = []
    if p.rooms:
        facts.append(f"🚪 {p.rooms} rooms")
    if p.sqm:
        facts.append(f"📐 {p.sqm:.0f} sqm")
    if p.floor:
        facts.append(f"🏢 floor {esc(p.floor)}")
    location = " · ".join(esc(x) for x in (p.city, p.zone, p.address) if x)
    sqm_span = (
        f'<span class="sqm">{sqm_price:,} €/sqm</span>'.replace(",", ".") if sqm_price else ""
    )
    hist = ""
    if len(p.price_history) > 0:
        parts = " → ".join(_fmt_price(h.new_price, p.contract) for h in p.price_history)
        hist = f'<div class="hist">📉 {_fmt_price(p.first_price, p.contract)} → {parts}</div>'
    links = "".join(
        f'<a href="{html_lib.escape(l.url)}" target="_blank" rel="noreferrer">{esc(l.portal)} ↗</a>'
        for l in p.listings
    )
    target = ""
    low = getattr(p, "target_price_low", None)
    high = getattr(p, "target_price_high", None)
    if low and high:
        target = (
            f'<div class="hist">💬 Suggested proposal: '
            f"{_fmt_price(low, p.contract)} – {_fmt_price(high, p.contract)}</div>"
        )
    return (
        f'<div class="card">{img}<div class="body">'
        f'<div><span class="price">{_fmt_price(p.current_min_price, p.contract)}</span>{sqm_span}</div>'
        f'<div class="title">{esc(p.title or "Untitled")}</div>'
        f'<div class="loc">📍 {location or "—"}</div>'
        f'<div class="badges">{"".join(badges)}</div>'
        f'<div class="facts">{" · ".join(facts)}</div>'
        f"{hist}{target}"
        f'<div class="links">{links}</div>'
        f"</div></div>"
    )


def properties_to_html(props: list[Property], title: str) -> str:
    cards = "\n".join(_card_html(p) for p in props)
    generated = f"{datetime.now(UTC):%Y-%m-%d %H:%M UTC}"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html_lib.escape(title)}</title><style>{_HTML_STYLE}</style></head>"
        f"<body><h1>{html_lib.escape(title)}</h1>"
        f'<div class="meta">{len(props)} properties · generated {generated}</div>'
        f'<div class="grid">{cards}</div></body></html>'
    )


# --- Print dossier: the report you take to the bank or to a viewing ----------
#
# There is no PDF library here, and that is a decision rather than a shortcut.
# Rendering server-side would mean either a second layout in a foreign drawing
# model (reportlab, fpdf2) — a copy of this file's formatting that would drift
# from it, exactly what the "one fact, one implementation" convention exists to
# prevent — or a system toolchain the two shipping targets cannot both carry
# (weasyprint wants GTK/Pango, which the frozen Windows build has no way to
# bundle). The gallery settles it either way: the photos are remote portal CDN
# URLs, so a server-side renderer has to *download* them, and that is portal
# traffic outside AdProbe on the residential IP the scheduled scans depend on.
# The browser already fetches those same images for the HTML dossier, so it
# lays the pages out and its own "Save as PDF" writes the file: one layout, no
# dependency, and not one request from the backend.

_COMMUTE_MODES = {"car": "by car", "foot": "on foot", "bike": "by bike"}

# Written before the visit and filled in during it, so the items are the ones
# whose answer is only knowable on site — and which cost real money when they
# surface after the deed instead. Deliberately generic: no assumption about the
# city, the portal or the kind of property.
_VIEWING_CHECKLIST = (
    "Actual floor, and whether the lift reaches it",
    "Monthly building fees, and what they cover",
    "Extraordinary works voted, planned or under discussion",
    "Heating: type, autonomous or central, last service",
    "Energy class, and the real bills of the past year",
    "Window frames and glazing: draughts, condensation, noise",
    "Damp, cracks or mould — corners, ceilings, behind the furniture",
    "Street and neighbour noise; ask what an evening sounds like",
    "Natural light and aspect, room by room",
    "Cellar, attic, parking, garden: included or priced apart",
    "Land registry plan matches what is actually built",
    "Occupancy: free on deed, or a sitting tenant with a running lease",
    "Works needed before moving in, and a rough figure for them",
    "Time on foot to transport, school, shops",
)

# Print-first, but the document opens in a browser tab before it reaches the
# print dialog, so it has to read on screen too. `print-color-adjust: exact`
# keeps the badges filled: browsers drop background colours when printing
# unless asked not to, and a "22% below market" chip printed white on white
# says nothing.
_PRINT_STYLE = """
@page { size: A4; margin: 14mm 12mm 16mm; }
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  margin: 0; background: #fff; color: #0f172a; font-size: 12px; line-height: 1.45;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.sheet { max-width: 820px; margin: 0 auto; padding: 24px; }
.hint { background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af;
  border-radius: 10px; padding: 10px 14px; margin-bottom: 20px; font-size: 13px; }
.cover h1 { font-size: 22px; margin: 0 0 4px; }
.cover .meta { color: #64748b; font-size: 12px; }
.property { border-top: 2px solid #0f172a; padding-top: 12px; margin-top: 26px;
  break-inside: auto; }
.property:first-of-type { margin-top: 18px; }
.head { display: flex; justify-content: space-between; align-items: baseline;
  gap: 12px; flex-wrap: wrap; }
.head .price { font-size: 21px; font-weight: 700; }
.head .idx { color: #64748b; font-size: 11px; letter-spacing: .06em; }
h2 { font-size: 15px; margin: 6px 0 2px; }
.loc { color: #475569; font-size: 12px; }
.badges { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 4px; }
.badge { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 8px;
  border: 1px solid transparent; }
.good { background: #d1fae5; color: #065f46; border-color: #a7f3d0; }
.warn { background: #fef3c7; color: #92400e; border-color: #fde68a; }
.muted { background: #e2e8f0; color: #334155; border-color: #cbd5e1; }
h3 { font-size: 11px; text-transform: uppercase; letter-spacing: .07em;
  color: #64748b; margin: 14px 0 6px; }
.gallery { display: grid; gap: 6px; grid-template-columns: repeat(3, 1fr); }
.gallery img { width: 100%; height: 118px; object-fit: cover; background: #e2e8f0;
  border-radius: 8px; border: 1px solid #e2e8f0; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 4px 8px 4px 0; vertical-align: top;
  border-bottom: 1px solid #f1f5f9; }
th { color: #64748b; font-weight: 600; width: 34%; }
table.hist th { width: auto; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 0 28px; }
.notes { white-space: pre-wrap; background: #f8fafc; border: 1px solid #e2e8f0;
  border-radius: 8px; padding: 8px 10px; }
ul.sources { margin: 0; padding-left: 16px; }
ul.sources li { margin-bottom: 2px; word-break: break-all; }
.check { list-style: none; margin: 0; padding: 0; column-count: 2; column-gap: 24px; }
.check li { break-inside: avoid; margin-bottom: 5px; padding-left: 20px;
  position: relative; }
.check li::before { content: ""; position: absolute; left: 0; top: 1px;
  width: 11px; height: 11px; border: 1.2px solid #64748b; border-radius: 2px; }
.rule { border-bottom: 1px solid #cbd5e1; height: 17px; }
.foot { color: #94a3b8; font-size: 10px; margin-top: 10px; }
@media print { .hint { display: none; }
  .property { break-before: page; }
  .property:first-of-type { break-before: auto; } }
"""


def _print_facts(p: Property) -> str:
    esc = html_lib.escape
    sqm_price = _sqm_price(p)
    rows: list[tuple[str, str]] = [
        ("Contract", "Rent" if p.contract == "rent" else "Sale"),
        ("Asking price", _fmt_price(p.current_min_price, p.contract)),
        ("€/sqm", f"{sqm_price:,} €".replace(",", ".") if sqm_price else "—"),
        ("Surface", f"{p.sqm:.0f} sqm" if p.sqm else "—"),
        ("Rooms", str(p.rooms) if p.rooms else "—"),
        ("Floor", esc(p.floor) or "—"),
        ("City", esc(p.city) or "—"),
        ("Zone", esc(p.zone) or "—"),
        ("Address", esc(p.address) or "—"),
        ("First seen", _fmt_date(p.first_seen_at)),
    ]
    median = getattr(p, "area_median_sqm_price", None)
    if median:
        scope = getattr(p, "area_median_scope", None) or "area"
        delta = getattr(p, "sqm_price_delta_pct", None)
        value = f"{median:,.0f} €/sqm".replace(",", ".") + f" ({scope})"
        if delta is not None:
            value += f" · this one is {delta:+.1f}%"
        rows.append(("Area median", value))
    low = getattr(p, "target_price_low", None)
    high = getattr(p, "target_price_high", None)
    if low and high:
        rows.append(
            (
                "Suggested proposal",
                f"{_fmt_price(low, p.contract)} – {_fmt_price(high, p.contract)}",
            )
        )
    cells = "".join(f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in rows)
    return f"<table>{cells}</table>"


def _print_property_html(p: Property, index: int, total: int) -> str:
    esc = html_lib.escape
    parts: list[str] = []
    location = " · ".join(esc(x) for x in (p.city, p.zone, p.address) if x)
    parts.append(
        f'<div class="head"><span class="price">'
        f"{_fmt_price(p.current_min_price, p.contract)}</span>"
        f'<span class="idx">{index} of {total}</span></div>'
        f"<h2>{esc(p.title or 'Untitled')}</h2>"
        f'<div class="loc">{location or "—"}</div>'
    )

    badges = []
    deal = getattr(p, "deal_score", None)
    if deal is not None and getattr(p, "deal_label", None) != "fair":
        cls = "good" if deal > 0 else "warn"
        side = "below" if deal > 0 else "above"
        badges.append(f'<span class="badge {cls}">{abs(deal)}% {side} market</span>')
    match = getattr(p, "match_score", None)
    if match is not None:
        badges.append(f'<span class="badge muted">{match}% match</span>')
    if p.is_favorite:
        badges.append('<span class="badge muted">★ favourite</span>')
    if p.status != "active":
        badges.append(f'<span class="badge muted">{esc(p.status)}</span>')
    if badges:
        parts.append(f'<div class="badges">{"".join(badges)}</div>')

    photos = _gallery_urls(p)
    if photos:
        imgs = "".join(f'<img src="{esc(u)}" alt="" loading="lazy">' for u in photos)
        parts.append(f'<h3>Photos</h3><div class="gallery">{imgs}</div>')

    history = _history_rows(p)
    hist_html = ""
    if history:
        body = "".join(
            f"<tr><td>{when}</td><td>{price}</td><td>{change}</td></tr>"
            for when, price, change in history
        )
        hist_html = (
            "<h3>Price history</h3>"
            '<table class="hist"><tr><th>Date</th><th>Price</th><th>Change</th></tr>'
            f"{body}</table>"
        )
    parts.append(
        f'<div class="cols"><div><h3>Key facts</h3>{_print_facts(p)}</div>'
        f"<div>{hist_html}</div></div>"
    )

    legs = getattr(p, "commutes", None) or []
    if legs:
        items = "".join(
            f"<tr><th>{esc(str(leg.get('name', '')))}</th><td>"
            f"{round((leg.get('duration_s') or 0) / 60)} min "
            f"{_COMMUTE_MODES.get(str(leg.get('mode')), '')} · "
            f"{(leg.get('distance_m') or 0) / 1000:.1f} km</td></tr>"
            for leg in legs
        )
        parts.append(f"<h3>Commute</h3><table>{items}</table>")

    if p.notes:
        parts.append(f'<h3>Your notes</h3><div class="notes">{esc(p.notes)}</div>')

    if p.listings:
        links = "".join(
            f"<li>{esc(l.portal)}"
            + (f" — {esc(l.agency)}" if l.agency else "")
            + f": {esc(l.url)}</li>"
            for l in p.listings
        )
        parts.append(f'<h3>Sources</h3><ul class="sources">{links}</ul>')

    checks = "".join(f"<li>{item}</li>" for item in _VIEWING_CHECKLIST)
    rules = '<div class="rule"></div>' * 4
    parts.append(
        f'<h3>Viewing checklist</h3><ul class="check">{checks}</ul>'
        f"<h3>Notes from the viewing</h3>{rules}"
    )
    return f'<section class="property">{"".join(parts)}</section>'


def properties_to_print_html(props: list[Property], title: str) -> str:
    """A paginated report — one property per page — that prints itself.

    Served inline rather than as a download: the browser opens it, the load
    handler below raises the print dialog, and "Save as PDF" produces the file.
    That one line is the only script in the document, and every scraped field
    around it is escaped exactly as in the HTML dossier.
    """
    esc = html_lib.escape
    total = len(props)
    pages = "\n".join(_print_property_html(p, i, total) for i, p in enumerate(props, start=1))
    generated = f"{datetime.now(UTC):%Y-%m-%d %H:%M UTC}"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(title)}</title><style>{_PRINT_STYLE}</style></head>"
        f'<body><div class="sheet">'
        '<div class="hint">The print dialog should open by itself — choose '
        '<strong>Save as PDF</strong> as the destination. Enable "Background '
        'graphics" to keep the badges filled.</div>'
        f'<div class="cover"><h1>{esc(title)}</h1>'
        f'<div class="meta">{total} properties · generated {generated}</div></div>'
        f"{pages}"
        '<div class="foot">Asking prices as advertised on the portals, not '
        "valuations.</div>"
        "</div>"
        "<script>window.addEventListener('load', function () { window.print(); });</script>"
        "</body></html>"
    )
