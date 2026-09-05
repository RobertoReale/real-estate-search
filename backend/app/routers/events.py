"""The one route the dashboard keeps open: `GET /api/events`.

What it carries and why there is a single sampler behind it is
`services/events.py`. What lives here is only the HTTP shape of it — the
Server-Sent Events content type, the headers a long-lived response needs to
survive the things that sit between a browser and this process, and the
detection of a client that has gone.
"""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..services.events import hub

router = APIRouter()


@router.get(
    "/api/events",
    responses={200: {"content": {"text/event-stream": {}}, "description": "The event stream"}},
    response_class=StreamingResponse,
)
async def event_stream(request: Request) -> StreamingResponse:
    """Push, instead of the four timers the dashboard used to run.

    Outbound-only and same-origin (invariant 14): the browser opens this and the
    server writes down it. There is no port to open, no address to register and
    nothing for anything outside this machine to call. The optional
    `api_auth_token` gate applies exactly as it does to every other `/api` route
    — this handler does nothing special to earn it, and must not.
    """

    async def body() -> AsyncIterator[str]:
        async for chunk in hub.subscribe():
            # A stream is only noticed as dead when something is written to it,
            # so the heartbeat is also what bounds how long a closed tab is
            # still counted as a subscriber.
            if await request.is_disconnected():
                return
            yield chunk

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # Nginx and friends buffer a response by default, which for a stream
            # means the first frame arrives when the last one does.
            "X-Accel-Buffering": "no",
        },
    )
