#!/usr/bin/env python3
"""Build the TwoWayFanChart addon archive and listing files.

Usage:
    python3 build_addon.py

Produces:
    gramps60/download/TwoWayFanChart.addon.tgz
    gramps60/listings/addons-en.json
    gramps60/listings/addons-fr.json
"""
import glob
import gzip
import json
import os
import tarfile

ADDON = "TwoWayFanChart"
GRAMPS_VERSION = "6.0"
VERSION = "1.2.33"

# ── Build .addon.tgz ──

files = []

# From MANIFEST
manifest_path = f"{ADDON}/MANIFEST"
if os.path.isfile(manifest_path):
    with open(manifest_path) as f:
        for line in f:
            line = line.strip()
            if line and os.path.isfile(line):
                files.append(line)

# From patterns
for patt in [f"{ADDON}/*.py"]:
    for f in glob.glob(patt):
        if f not in files:
            files.append(f)

# Deduplicate
seen = set()
unique_files = []
for f in files:
    if f not in seen:
        seen.add(f)
        unique_files.append(f)

download_dir = f"gramps60/download"
os.makedirs(download_dir, exist_ok=True)

def tar_filt(tinfo):
    """Normalize tar metadata so identical sources produce identical bytes."""
    tinfo.uid = 0
    tinfo.gid = 0
    tinfo.uname = tinfo.gname = "gramps"
    tinfo.mtime = 0
    if tinfo.isfile():
        tinfo.mode = 0o644
    elif tinfo.isdir():
        tinfo.mode = 0o755
    tinfo.pax_headers = {}
    return tinfo

tgz_path = f"{download_dir}/{ADDON}.addon.tgz"
with open(tgz_path, "wb") as raw_archive:
    with gzip.GzipFile(fileobj=raw_archive, mode="wb", mtime=0) as compressed:
        with tarfile.open(
            fileobj=compressed, mode="w", format=tarfile.GNU_FORMAT
        ) as tar:
            for f in sorted(unique_files):
                tar.add(f, filter=tar_filt)

print(f"Built: {tgz_path} ({os.path.getsize(tgz_path)} bytes)")

# ── Build listing JSON files ──

listings_dir = "gramps60/listings"
os.makedirs(listings_dir, exist_ok=True)

listings = {
    "en": {
        "n": "Two-Way Fan Chart",
        "i": ADDON,
        "t": 0,  # REPORT
        "d": "Generates a bidirectional fan chart with ancestors, descendants, and portraits around a center family.",
        "v": VERSION,
        "g": GRAMPS_VERSION,
        "s": 3,  # STABLE
        "z": f"{ADDON}.addon.tgz",
        "h": "https://github.com/grostim/gramps-two-way-fan-chart",
    },
    "fr": {
        "n": "Éventail généalogique bidirectionnel",
        "i": ADDON,
        "t": 0,
        "d": "Génère un éventail généalogique bidirectionnel avec ascendants, descendants et portraits autour d'un couple central.",
        "v": VERSION,
        "g": GRAMPS_VERSION,
        "s": 3,
        "z": f"{ADDON}.addon.tgz",
        "h": "https://github.com/grostim/gramps-two-way-fan-chart",
    },
}

for lang, entry in listings.items():
    path = f"{listings_dir}/addons-{lang}.json"
    with open(path, "w", encoding="utf-8", newline="") as fp:
        json.dump([entry], fp, indent=1, ensure_ascii=False)
    print(f"Built: {path}")

print("\nDone! To install in Gramps:")
print(f"  1. Point Gramps addon URL to: https://raw.githubusercontent.com/grostim/gramps-two-way-fan-chart/main/gramps60")
print(f"  2. Or install manually: Edit → Plugin Manager → Install from file → {tgz_path}")