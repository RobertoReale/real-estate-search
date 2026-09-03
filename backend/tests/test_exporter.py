"""Offline export: CSV / Markdown / self-contained HTML dossier.

The functions are pure over a list of Property objects, so most tests build
transient ones. Two things matter beyond "it renders": HTML escaping (a listing
title is attacker-influenced text going into a file a user will open) and that
the transient Deal/Match annotations survive into the output when present.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Listing, PriceHistory, Property
from app.services.exporter import (
    properties_to_csv,
    properties_to_html,
    properties_to_markdown,
    properties_to_print_html,
)


def _prop(
    title="Trilocale", price=300_000, favorite=False, deal=None, match=None, history=None, image=""
) -> Property:
    p = Property(
        fingerprint="f",
        title=title,
        city="Milano",
        zone="Isola",
        address="Via Test 1",
        contract="sale",
        current_min_price=price,
        first_price=price,
        sqm=100.0,
        rooms=3,
        floor="2",
        status="active",
        is_favorite=favorite,
        image_url=image,
        first_seen_at=datetime.now(UTC),
    )
    p.listings = [
        Listing(
            portal="immobiliare",
            portal_id="1",
            url="https://www.immobiliare.it/annunci/1/",
            agency="Studio Rossi",
        )
    ]
    p.price_history = [PriceHistory(old_price=o, new_price=n) for o, n in (history or [])]
    if deal is not None:
        p.deal_score = deal
        p.deal_label = "undervalued" if deal > 0 else "overpriced"
    p.match_score = match
    return p


def test_csv_has_header_and_a_row_per_property():
    csv_text = properties_to_csv([_prop(title="A"), _prop(title="B")])
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("Title,City,Zone")
    assert len(lines) == 3  # header + 2
    assert "A" in lines[1] and "B" in lines[2]


def test_csv_includes_deal_and_match_when_annotated():
    csv_text = properties_to_csv([_prop(deal=16, match=92)])
    row = csv_text.strip().splitlines()[1]
    assert "16" in row and "92" in row


def test_markdown_lists_price_history_and_links():
    md = properties_to_markdown([_prop(history=[(340_000, 300_000)])], "My shortlist")
    assert md.startswith("# My shortlist")
    assert "## Trilocale" in md
    assert "Price history:" in md
    assert "immobiliare.it/annunci/1" in md


def test_html_is_self_contained_and_escapes_titles():
    """The title comes from a portal listing — untrusted text. It must be HTML
    -escaped, or a crafted title would inject markup into the dossier the user
    opens in their browser."""
    html = properties_to_html([_prop(title="<script>alert(1)</script>")], "Dossier")
    assert html.startswith("<!doctype html>")
    assert "<style>" in html  # CSS inlined, not linked -> offline
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_html_renders_image_and_badges_when_present():
    html = properties_to_html([_prop(deal=16, match=92, image="http://x/y.jpg")], "Dossier")
    assert 'src="http://x/y.jpg"' in html
    assert "below market" in html  # deal badge
    assert "92% match" in html


def test_empty_export_still_valid():
    assert properties_to_csv([]).startswith("Title,")
    assert "0 properties" in properties_to_markdown([], "Empty")
    assert "<!doctype html>" in properties_to_html([], "Empty")


# --- endpoint wiring ---------------------------------------------------------


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def test_export_endpoint_sets_attachment_headers(db):
    from app.routers.properties import export_properties

    p = Property(
        fingerprint="f",
        title="Casa",
        city="Milano",
        contract="sale",
        current_min_price=250_000,
        sqm=80.0,
        status="active",
    )
    p.listings = [Listing(portal="immobiliare", portal_id="9", url="u")]
    db.add(p)
    db.commit()

    # the Query(...)-defaulted params must be passed explicitly when the
    # endpoint function is called directly (no FastAPI to resolve them)
    resp = export_properties(
        db=db,
        fmt="csv",
        status="active",
        contract=None,
        sort="newest",
        floor_band=None,
        portal=None,
        deal=None,
        center_lat=None,
        center_lng=None,
        radius_m=None,
    )
    assert (resp.media_type or "").startswith("text/csv")
    disposition = resp.headers["content-disposition"]
    assert disposition.startswith("attachment") and disposition.endswith('.csv"')
    assert b"Casa" in resp.body


def test_markdown_escapes_scraped_html():
    """Regression: title/location/agency went into the Markdown dossier raw.
    Many renderers (VS Code preview, Obsidian) pass HTML through, so a scraped
    title containing an <img onerror=…> became live markup on open."""
    md = properties_to_markdown([_prop(title="<img src=x onerror=alert(1)>Attico")], "S")
    assert "<img" not in md
    assert "&lt;img" in md


def test_csv_neutralizes_formula_injection():
    """Regression: a scraped title starting with "=" executes as a formula
    when the CSV is opened in Excel (CSV/formula injection). Text fields get
    the conventional quote prefix."""
    csv_text = properties_to_csv([_prop(title="=HYPERLINK(evil)")])
    row = csv_text.strip().splitlines()[1]
    assert "'=HYPERLINK" in row


def test_html_dossier_will_not_link_a_scripted_url():
    """Regression: a listing's URL is portal-supplied text too — the scrapers
    read it off an `href` or out of the page's own JSON (`seo.url`) — and the
    dossier turned it into `<a href="…">`. Escaping keeps it inside the
    attribute and does nothing about the scheme, so `javascript:` was a live
    link in a file the user opens from their own disk. Only http(s) is a URL a
    portal listing can honestly have; anything else renders as no link."""
    p = _prop()
    p.listings = [
        Listing(portal="immobiliare", portal_id="1", url="javascript:alert(document.cookie)")
    ]
    p.image_url = "javascript:alert(1)"
    html = properties_to_html([p], "Dossier")
    assert "javascript:" not in html
    assert "<a href" not in html  # the one listing had nothing linkable
    assert "<img" not in html

    # ...and an ordinary listing is untouched
    p.listings = [Listing(portal="immobiliare", portal_id="1", url="https://x.example/annunci/1/")]
    assert 'href="https://x.example/annunci/1/"' in properties_to_html([p], "Dossier")


def test_print_dossier_gallery_drops_a_scripted_image_url():
    """The gallery is the print report's only URL in an attribute, and it comes
    from the same untrusted place."""
    p = _prop(image="javascript:alert(1)")
    p.listings = [
        Listing(portal="idealista", portal_id="2", url="u2", image_url="https://x.example/a.jpg")
    ]
    html = properties_to_print_html([p], "D")
    assert "javascript:" not in html
    assert 'src="https://x.example/a.jpg"' in html


# --- print dossier (the "save as PDF" path) ----------------------------------


def test_print_dossier_paginates_and_prints_itself():
    """The PDF is produced by the browser's own print-to-PDF, so two things
    carry the whole feature: one page per property, and the dialog opening
    without the user hunting for Ctrl+P."""
    html = properties_to_print_html([_prop(title="A"), _prop(title="B")], "Dossier")
    assert html.startswith("<!doctype html>")
    assert html.count('<section class="property">') == 2
    assert "break-before: page" in html
    assert "window.print()" in html


def test_print_dossier_escapes_scraped_text():
    """Same untrusted-text rule as the HTML dossier: the title comes from a
    portal listing, and this document is opened in a browser."""
    html = properties_to_print_html([_prop(title="<script>alert(1)</script>")], "D")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    # our own print call is the only script the document may contain
    assert html.count("<script>") == 1


def test_print_dossier_gallery_collects_every_ad_photo():
    """A merged property is the point: each agency's ad brings its own photo,
    so the merge is what turns one thumbnail into a gallery. Duplicates across
    ads must collapse rather than print the same picture twice."""
    p = _prop(image="http://x/cover.jpg")
    p.listings = [
        Listing(portal="immobiliare", portal_id="1", url="u1", image_url="http://x/a.jpg"),
        Listing(portal="idealista", portal_id="2", url="u2", image_url="http://x/b.jpg"),
        Listing(portal="idealista", portal_id="3", url="u3", image_url="http://x/cover.jpg"),
    ]
    html = properties_to_print_html([p], "D")
    for url in ("http://x/cover.jpg", "http://x/a.jpg", "http://x/b.jpg"):
        assert f'src="{url}"' in html
    assert html.count('src="http://x/cover.jpg"') == 1


def test_print_dossier_shows_the_price_timeline():
    """`first_price` and `price_history` each tell half of it (invariant 6),
    and the drop percentage is what a negotiation actually leans on."""
    html = properties_to_print_html([_prop(history=[(340_000, 300_000)])], "D")
    assert "Price history" in html
    assert "first seen" in html
    assert "-11.8%" in html


def test_print_dossier_carries_the_viewing_checklist():
    html = properties_to_print_html([_prop()], "D")
    assert "Viewing checklist" in html
    assert "Monthly building fees, and what they cover" in html
    assert "Notes from the viewing" in html


def test_print_dossier_includes_annotations_when_present():
    """Market position, deal score and commute legs are transient annotations:
    absent when they were not computed, printed when they were."""
    p = _prop(deal=16, match=92)
    p.area_median_sqm_price = 4000.0
    p.area_median_scope = "zone"
    p.sqm_price_delta_pct = -25.0
    p.commutes = [{"name": "Office", "mode": "foot", "distance_m": 1500.0, "duration_s": 1080.0}]
    html = properties_to_print_html([p], "D")
    assert "16% below market" in html
    assert "92% match" in html
    # The median row says whose figure it is: the OMI band prints beside it and
    # the two must never read as one measurement (invariant 22).
    assert "Similar listings ask" in html and "-25.0%" in html
    assert "18 min on foot" in html and "1.5 km" in html


def test_print_dossier_without_annotations_omits_those_sections():
    html = properties_to_print_html([_prop()], "D")
    assert "Similar listings ask" not in html
    assert "Commute" not in html
    assert "Your notes" not in html


def test_print_dossier_empty_is_still_valid():
    html = properties_to_print_html([], "Empty")
    assert html.startswith("<!doctype html>")
    assert "0 properties" in html


def test_pdf_export_is_served_inline_not_downloaded(db):
    """A print-ready document must be *opened* to print itself. Downloaded, it
    would sit in the Downloads folder having produced no PDF at all."""
    from app.routers.properties import export_properties

    p = Property(
        fingerprint="f",
        title="Casa",
        city="Milano",
        contract="sale",
        current_min_price=250_000,
        sqm=80.0,
        status="active",
    )
    p.listings = [Listing(portal="immobiliare", portal_id="9", url="u")]
    db.add(p)
    db.commit()

    resp = export_properties(
        db=db,
        fmt="pdf",
        status="active",
        contract=None,
        sort="newest",
        floor_band=None,
        portal=None,
        deal=None,
        center_lat=None,
        center_lng=None,
        radius_m=None,
    )
    assert (resp.media_type or "").startswith("text/html")
    assert resp.headers["content-disposition"].startswith("inline")
    assert b"Viewing checklist" in resp.body
