"""Offline export of a property shortlist as CSV, Markdown, or a self-contained
HTML dossier.

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
from datetime import datetime, timezone

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


def _primary_url(p: Property) -> str:
    return p.listings[0].url if p.listings else ""


def _sources(p: Property) -> str:
    return " | ".join(l.url for l in p.listings)


def properties_to_csv(props: list[Property]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "Title", "City", "Zone", "Address", "Contract", "Price", "Sqm",
        "Rooms", "Floor", "EUR/sqm", "Status", "Deal score", "Match score",
        "Favorite", "First seen", "URLs",
    ])
    for p in props:
        writer.writerow([
            p.title, p.city, p.zone, p.address, p.contract,
            p.current_min_price if p.current_min_price is not None else "",
            p.sqm if p.sqm is not None else "",
            p.rooms if p.rooms is not None else "",
            p.floor, _sqm_price(p) or "", p.status,
            getattr(p, "deal_score", None) if getattr(p, "deal_score", None) is not None else "",
            getattr(p, "match_score", None) if getattr(p, "match_score", None) is not None else "",
            "yes" if p.is_favorite else "no",
            p.first_seen_at.date().isoformat() if p.first_seen_at else "",
            _sources(p),
        ])
    return buffer.getvalue()


def properties_to_markdown(props: list[Property], title: str) -> str:
    lines = [f"# {title}", "",
             f"_{len(props)} properties · generated "
             f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}_", ""]
    for p in props:
        sqm_price = _sqm_price(p)
        lines.append(f"## {p.title or 'Untitled'}")
        location = " · ".join(x for x in (p.city, p.zone, p.address) if x)
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
            facts.append(f"floor {p.floor}")
        if facts:
            lines.append(f"- **Details:** {', '.join(facts)}")
        deal = getattr(p, "deal_score", None)
        if deal is not None and getattr(p, "deal_label", None) != "fair":
            lines.append(f"- **Deal score:** {deal:+d}% "
                         f"({getattr(p, 'deal_label', '')})")
        match = getattr(p, "match_score", None)
        if match is not None:
            lines.append(f"- **Match:** {match}%")
        if len(p.price_history) > 0:
            hist = ", ".join(
                f"{_fmt_price(h.old_price, p.contract)}→"
                f"{_fmt_price(h.new_price, p.contract)}"
                for h in p.price_history
            )
            lines.append(f"- **Price history:** {hist}")
        for l in p.listings:
            agency = f" — {l.agency}" if l.agency else ""
            lines.append(f"- **{l.portal}**{agency}: {l.url}")
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
    img = (f'<img src="{esc(p.image_url)}" alt="" loading="lazy">'
           if p.image_url else "")
    badges = []
    deal = getattr(p, "deal_score", None)
    if deal is not None and getattr(p, "deal_label", None) != "fair":
        cls = "good" if deal > 0 else "warn"
        badges.append(f'<span class="badge {cls}">🎯 {abs(deal)}% '
                      f'{"below" if deal > 0 else "above"} market</span>')
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
    sqm_span = (f'<span class="sqm">{sqm_price:,} €/sqm</span>'.replace(",", ".")
                if sqm_price else "")
    hist = ""
    if len(p.price_history) > 0:
        parts = " → ".join(_fmt_price(h.new_price, p.contract)
                           for h in p.price_history)
        hist = f'<div class="hist">📉 {_fmt_price(p.first_price, p.contract)} → {parts}</div>'
    links = "".join(
        f'<a href="{html_lib.escape(l.url)}" target="_blank" rel="noreferrer">'
        f'{esc(l.portal)} ↗</a>'
        for l in p.listings
    )
    target = ""
    low = getattr(p, "target_price_low", None)
    high = getattr(p, "target_price_high", None)
    if low and high:
        target = (f'<div class="hist">💬 Suggested proposal: '
                  f'{_fmt_price(low, p.contract)} – {_fmt_price(high, p.contract)}</div>')
    return (
        f'<div class="card">{img}<div class="body">'
        f'<div><span class="price">{_fmt_price(p.current_min_price, p.contract)}</span>{sqm_span}</div>'
        f'<div class="title">{esc(p.title or "Untitled")}</div>'
        f'<div class="loc">📍 {location or "—"}</div>'
        f'<div class="badges">{"".join(badges)}</div>'
        f'<div class="facts">{" · ".join(facts)}</div>'
        f'{hist}{target}'
        f'<div class="links">{links}</div>'
        f'</div></div>'
    )


def properties_to_html(props: list[Property], title: str) -> str:
    cards = "\n".join(_card_html(p) for p in props)
    generated = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{html_lib.escape(title)}</title><style>{_HTML_STYLE}</style></head>"
        f"<body><h1>{html_lib.escape(title)}</h1>"
        f'<div class="meta">{len(props)} properties · generated {generated}</div>'
        f'<div class="grid">{cards}</div></body></html>'
    )
