"""Offline export: CSV / Markdown / self-contained HTML dossier.

The functions are pure over a list of Property objects, so most tests build
transient ones. Two things matter beyond "it renders": HTML escaping (a listing
title is attacker-influenced text going into a file a user will open) and that
the transient Deal/Match annotations survive into the output when present.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Listing, PriceHistory, Property
from app.services.exporter import (
    properties_to_csv, properties_to_html, properties_to_markdown,
)


def _prop(title="Trilocale", price=300_000, favorite=False, deal=None,
          match=None, history=None, image="") -> Property:
    p = Property(fingerprint="f", title=title, city="Milano", zone="Isola",
                 address="Via Test 1", contract="sale",
                 current_min_price=price, first_price=price, sqm=100.0,
                 rooms=3, floor="2", status="active", is_favorite=favorite,
                 image_url=image, first_seen_at=datetime.now(timezone.utc))
    p.listings = [Listing(portal="immobiliare", portal_id="1",
                          url="https://www.immobiliare.it/annunci/1/",
                          agency="Studio Rossi")]
    p.price_history = [
        PriceHistory(old_price=o, new_price=n) for o, n in (history or [])
    ]
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
    md = properties_to_markdown(
        [_prop(history=[(340_000, 300_000)])], "My shortlist")
    assert md.startswith("# My shortlist")
    assert "## Trilocale" in md
    assert "Price history:" in md
    assert "immobiliare.it/annunci/1" in md


def test_html_is_self_contained_and_escapes_titles():
    """The title comes from a portal listing — untrusted text. It must be HTML
    -escaped, or a crafted title would inject markup into the dossier the user
    opens in their browser."""
    html = properties_to_html([_prop(title="<script>alert(1)</script>")],
                              "Dossier")
    assert html.startswith("<!doctype html>")
    assert "<style>" in html  # CSS inlined, not linked -> offline
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_html_renders_image_and_badges_when_present():
    html = properties_to_html([_prop(deal=16, match=92, image="http://x/y.jpg")],
                              "Dossier")
    assert 'src="http://x/y.jpg"' in html
    assert "below market" in html   # deal badge
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
    from app.main import export_properties

    p = Property(fingerprint="f", title="Casa", city="Milano", contract="sale",
                 current_min_price=250_000, sqm=80.0, status="active")
    p.listings = [Listing(portal="immobiliare", portal_id="9", url="u")]
    db.add(p)
    db.commit()

    # the Query(...)-defaulted params must be passed explicitly when the
    # endpoint function is called directly (no FastAPI to resolve them)
    resp = export_properties(db=db, fmt="csv", status="active", contract=None,
                             sort="newest")
    assert (resp.media_type or "").startswith("text/csv")
    disposition = resp.headers["content-disposition"]
    assert disposition.startswith("attachment") and disposition.endswith('.csv"')
    assert b"Casa" in resp.body
