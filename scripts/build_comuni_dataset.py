"""Dev-only: regenerate the bundled Italian-municipality dataset.

Produces ``backend/app/data/comuni.sqlite`` — the offline gazetteer behind
``services/geo_reference.py`` (city detection + coordinate plausibility for
every Italian comune, not just the hand-listed Milan-area ones). The built
artifact is committed like a fixture: the runtime never fetches anything
(Raspberry-Pi/offline guarantee), this script runs only when we choose to
refresh the data.

Sources (both official/permanent):
  * ISTAT  "Elenco comuni italiani" CSV — the authoritative list of all
    ~7,900 municipalities (names incl. bilingual, province, region).
  * GeoNames postal dataset IT.zip — place name + lat/lng per postal code,
    averaged per (comune, province) into a centroid.

Usage:  python scripts/build_comuni_dataset.py  [--istat FILE] [--geonames FILE]
(the flags reuse pre-downloaded files; without them both sources are fetched).
"""

import argparse
import csv
import io
import re
import sqlite3
import sys
import unicodedata
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

ISTAT_URL = "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv"
GEONAMES_URL = "https://download.geonames.org/export/zip/IT.zip"
OUT_PATH = Path(__file__).resolve().parent.parent / "backend" / "app" / "data" / "comuni.sqlite"


def normalize(text: str) -> str:
    """Same shape as filter_engine._normalize: accent-insensitive, lowercase,
    collapsed whitespace. Kept copy-paste tiny here because this script must
    run without the backend package on the path."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().replace("-", " ").replace("'", "' ").split()).replace("' ", "'")


def fetch(url: str) -> bytes:
    print(f"downloading {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "comuni-dataset-builder/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def load_istat(raw: bytes) -> list[dict]:
    """Rows of {name, alt_name, province, province_sigla, region}."""
    text = raw.decode("latin-1")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    header = next(reader)
    idx = {}
    for i, col in enumerate(header):
        c = normalize(col)
        if c.startswith("denominazione in italiano"):
            idx["name"] = i
        elif c.startswith("denominazione altra lingua"):
            idx["alt"] = i
        elif c.startswith("denominazione regione"):
            idx["region"] = i
        elif c.startswith("denominazione dell'unita territoriale sovracomunale"):
            idx["province"] = i
        elif c.startswith("sigla automobilistica"):
            idx["sigla"] = i
    missing = {"name", "region", "province", "sigla"} - set(idx)
    if missing:
        raise SystemExit(f"ISTAT CSV: could not locate columns {missing} in header {header!r}")
    rows = []
    for row in reader:
        if len(row) <= idx["sigla"]:
            continue
        name = row[idx["name"]].strip()
        if not name:
            continue
        rows.append(
            {
                "name": name,
                "alt_name": row[idx.get("alt", idx["name"])].strip() if "alt" in idx else "",
                "province": row[idx["province"]].strip(),
                "province_sigla": row[idx["sigla"]].strip().upper(),
                "region": row[idx["region"]].strip(),
            }
        )
    return rows


def load_geonames_centroids(raw_zip: bytes) -> dict[tuple[str, str], tuple[float, float, int]]:
    """(normalized place name, province sigla) -> (lat, lng, postal_count).

    Coordinates are averaged over the postal codes sharing the name (GeoNames
    repeats one centroid per comune, so the average is that centroid). The
    postal-code COUNT is kept as a size proxy: Roma has ~74 CAPs, a village
    has 1, and geo_reference turns that into a per-comune plausibility radius
    — one flat radius either let "Milano" pins land in Cernusco (too wide) or
    rejected half of Rome (too tight). Postal rows cover frazioni too; we only
    ever *look up* by comune name, so extra place names are harmless."""
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as zf:
        text = zf.read("IT.txt").decode("utf-8")
    sums: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 11:
            continue
        place, sigla, lat, lng = parts[2], parts[6].strip().upper(), parts[9], parts[10]
        try:
            lat_f, lng_f = float(lat), float(lng)
        except ValueError:
            continue
        acc = sums[(normalize(place), sigla)]
        acc[0] += lat_f
        acc[1] += lng_f
        acc[2] += 1
    return {k: (v[0] / v[2], v[1] / v[2], int(v[2])) for k, v in sums.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--istat", type=Path, help="pre-downloaded ISTAT CSV")
    ap.add_argument("--geonames", type=Path, help="pre-downloaded GeoNames IT.zip")
    args = ap.parse_args()

    istat_raw = args.istat.read_bytes() if args.istat else fetch(ISTAT_URL)
    geonames_raw = args.geonames.read_bytes() if args.geonames else fetch(GEONAMES_URL)

    comuni = load_istat(istat_raw)
    centroids = load_geonames_centroids(geonames_raw)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if OUT_PATH.exists():
        OUT_PATH.unlink()
    con = sqlite3.connect(OUT_PATH)
    con.executescript(
        """
        CREATE TABLE comuni (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            province TEXT NOT NULL,
            province_sigla TEXT NOT NULL,
            region TEXT NOT NULL,
            lat REAL,
            lng REAL,
            postal_count INTEGER NOT NULL DEFAULT 0
        );
        -- one comune can be reachable under several spellings (bilingual
        -- names, "Firenze/Florence" is NOT in scope — only official forms)
        CREATE TABLE comune_names (
            name_norm TEXT NOT NULL,
            comune_id INTEGER NOT NULL REFERENCES comuni(id)
        );
        CREATE INDEX ix_comune_names ON comune_names(name_norm);
        """
    )

    matched = 0
    for i, c in enumerate(comuni, start=1):
        names = {normalize(c["name"])}
        if c["alt_name"]:
            names.add(normalize(c["alt_name"]))
            # "Bolzano/Bozen" — the combined form appears in listing text too
            names.add(normalize(f"{c['name']}/{c['alt_name']}"))
        # Everyday speech (and portal URLs) drop the connectives: "Reggio
        # nell'Emilia" is written "Reggio Emilia", "Reggio di Calabria" is
        # "Reggio Calabria". Index those variants too; ambiguity between two
        # comuni sharing an alias is resolved at lookup time, not here.
        for base_name in list(names):
            alias = re.sub(r"\bnell'|\b(?:di|nella|nel)\s+", "", base_name).strip()
            if alias and alias != base_name:
                names.add(alias)
        # GeoNames spells some comuni by their everyday form ("Reggio Emilia"),
        # so the centroid join tries every indexed variant, not just the
        # official ISTAT name.
        centroid = None
        for n in names:
            centroid = centroids.get((n, c["province_sigla"]))
            if centroid:
                break
        lat, lng, count = centroid if centroid else (None, None, 0)
        if centroid:
            matched += 1
        con.execute(
            "INSERT INTO comuni (id, name, province, province_sigla, region, lat, lng,"
            " postal_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (i, c["name"], c["province"], c["province_sigla"], c["region"], lat, lng, count),
        )
        for n in names:
            if n:
                con.execute("INSERT INTO comune_names (name_norm, comune_id) VALUES (?, ?)", (n, i))
    con.commit()
    n_names = con.execute("SELECT COUNT(*) FROM comune_names").fetchone()[0]
    con.close()
    size_kb = OUT_PATH.stat().st_size // 1024
    print(
        f"wrote {OUT_PATH}: {len(comuni)} comuni ({matched} with centroid, "
        f"{len(comuni) - matched} without), {n_names} name keys, {size_kb} KB"
    )
    if matched < len(comuni) * 0.9:
        print("WARNING: centroid coverage below 90% — check the GeoNames join", file=sys.stderr)


if __name__ == "__main__":
    main()
