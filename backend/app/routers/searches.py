"""Turning an intention into a portal search URL: the structured builder, its
reverse parser, and the natural-language assistant that feeds the builder.

Grouped apart from `profiles` on purpose — nothing here touches the database.
These three routes are pure functions over the search-URL grammar, and the
profile routes are the ones that persist the result.
"""

from fastapi import APIRouter

from .. import schemas
from ..services.query_parser import parse_query_auto
from ..services.search_builder import build_search_urls, parse_search_url

router = APIRouter()


@router.post("/api/search-builder")
def search_builder(data: schemas.SearchBuilderIn):
    """Generates ready-to-use search URLs for both portals from structured
    parameters, so the user does not have to copy/paste from the browser.

    Declared sync on purpose, like the availability check: with `verify` set
    this makes a live request to Idealista, and an `async def` would hold the
    event loop for its whole duration.
    """
    payload = data.model_dump()
    verify = payload.pop("verify", False)
    return build_search_urls(payload, verify=verify)


@router.post("/api/search-builder/parse", response_model=schemas.SearchBuilderParamsOut)
def search_builder_parse(data: schemas.UrlIn):
    """Extracts structured search builder parameters from a portal search URL."""
    return schemas.SearchBuilderParamsOut(**parse_search_url(data.url))


@router.post("/api/search-assistant", response_model=schemas.AssistantOut)
def search_assistant(data: schemas.AssistantQueryIn):
    """Turns a plain-language query into search-builder parameters.

    A query with disjunctions ("bilocale in zona X o trilocale in zona Y")
    yields one search per alternative. Never raises on an unparseable query:
    it answers with whatever it understood plus `warnings`, and the UI
    pre-fills the builder form so the user can correct it. URLs are built
    only when a city was identified — without one the portals would silently
    return all of Italy.
    """
    result = parse_query_auto(data.query)
    searches = []
    for search in result["searches"]:
        params = schemas.AssistantParams(**search["params"])
        searches.append(
            schemas.AssistantSearch(
                params=params,
                interpretation=search["interpretation"],
                notes=search.get("notes", []),
                warnings=search["warnings"],
                urls=(
                    schemas.SearchBuilderUrlsOut(**build_search_urls(params.model_dump()))
                    if params.city
                    else None
                ),
            )
        )
    return schemas.AssistantOut(searches=searches)
