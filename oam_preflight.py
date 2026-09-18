"""CLI for local OAM visual imagery preflight.

Usage:
  python oam_preflight.py inspect image.tif
  python oam_preflight.py validate image.tif
  python oam_preflight.py validate image.tif --epsg 32751

The CLI runs GDAL locally. It never uploads the raster.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from utils.oam_preflight import validate_gdalinfo


def run_gdalinfo(path: str) -> str:
    exe = shutil.which("gdalinfo")
    if not exe:
        raise RuntimeError("gdalinfo was not found on PATH. Install GDAL and reopen PowerShell.")
    result = subprocess.run([exe, "-json", path], capture_output=True, text=True)
    if result.returncode != 0:
        # Keep stderr useful while avoiding a second command.
        raise RuntimeError(result.stderr.strip() or f"gdalinfo failed with exit code {result.returncode}")
    return result.stdout


def print_result(result) -> None:
    print(f"STATUS: {result.status}")
    for check in result.checks:
        print(f"[{check.status}] {check.name}: {check.detail}")
    for note in result.notes:
        print(f"NOTE: {note}")
    if result.suggested_command:
        print("\nONE-COMMAND FIX / OAM-READY OUTPUT:")
        print(result.suggested_command)
    else:
        print("\nNO AUTOMATIC COMMAND GENERATED.")
        print("A missing/unknown CRS or unsupported band layout requires user input before a safe conversion can be generated.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Local OAM visual imagery preflight")
    sub = parser.add_subparsers(dest="action", required=True)

    for name in ("inspect", "validate"):
        p = sub.add_parser(name)
        p.add_argument("image", help="Local raster path")
        p.add_argument("--epsg", help="Target EPSG for reprojection, e.g. 32751")
        p.add_argument("--output", help="Output OAM-ready TIFF path")
        p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    args = parser.parse_args()
    try:
        raw = run_gdalinfo(args.image)
        if args.action == "inspect":
            print(raw)
            return 0
        result = validate_gdalinfo(raw, args.image, args.output, args.epsg)
        if args.json:
            print(json.dumps(result.as_dict(), indent=2))
        else:
            print_result(result)
        return 0 if result.status != "FAIL" else 2
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
