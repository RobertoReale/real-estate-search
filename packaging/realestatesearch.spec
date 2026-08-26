# PyInstaller spec for the Windows package. Built via scripts/build_release.py.
#
# ONE-FOLDER, not one-file. One-file re-extracts the whole bundle into a temp
# directory on every launch: slower, and it makes `sys._MEIPASS` change from run
# to run, which is precisely the trap config.py documents — anything resolved
# against the code would move or vanish. One-folder keeps the payload on disk
# and `_MEIPASS` stable, and the data still lives outside it (config.DATA_DIR).
#
# The datas below are not optional extras. Each one is something the app reads
# at run time and would fail on, mostly quietly:
#   - alembic.ini + alembic/  : database.ALEMBIC_INI/ALEMBIC_DIR. The migration
#                               step is fail-open, so a missing script directory
#                               would show up only as a warning in the log and a
#                               schema that never upgrades again.
#   - app/data/comuni.sqlite  : geo_reference's offline gazetteer. Without it,
#                               city detection degrades to "" everywhere, which
#                               silently blocks cross-portal merges (invariant 1).
#   - frontend/dist           : the dashboard itself (invariant 13's mount).
#   - icon-512.png            : the tray icon.

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent
BACKEND = ROOT / "backend"

# curl_cffi ships compiled libraries; missing them turns invariant 8's TLS
# impersonation into an ImportError on the first fetch.
curl_datas, curl_binaries, curl_hidden = collect_all("curl_cffi")

datas = [
    (str(BACKEND / "alembic.ini"), "."),
    (str(BACKEND / "alembic"), "alembic"),
    (str(BACKEND / "app" / "data"), "app/data"),
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    (str(ROOT / "frontend" / "public" / "icon-512.png"), "packaging"),
    *curl_datas,
]

hiddenimports = [
    # Imported by name, so nothing in the graph points at them.
    "app.main",
    "open_dashboard",
    *collect_submodules("uvicorn"),
    *collect_submodules("apscheduler"),
    "sqlalchemy.dialects.sqlite",
    *curl_hidden,
]

a = Analysis(
    [str(ROOT / "packaging" / "tray_app.py")],
    pathex=[str(BACKEND), str(ROOT / "scripts")],
    binaries=curl_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    # Optional by design (invariant 18) and ~300 MB of browser each: excluded so
    # a developer machine that happens to have them does not quadruple the
    # package. Their absence degrades to the manual cookie paste, as always.
    excludes=["playwright", "camoufox", "pytest", "hypothesis"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="RealEstateSearch",
    console=False,  # the tray icon is the interface; a console would be the bug
    icon=str(ROOT / "packaging" / "app.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="RealEstateSearch",
)
