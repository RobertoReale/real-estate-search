"""The REST surface, one module per cohesive group of routes.

`main.py` owns the app object, the middleware and the registration order; each
module here owns an `APIRouter` and declares its own paths in full (no
`prefix=`), so a route's URL is greppable from its decorator exactly as it was
when they all lived in one file.

`selection.py` is the exception: it is not a router but the shared property
query the grid, the map and the export all go through.
"""
