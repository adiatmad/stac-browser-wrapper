#!/usr/bin/env python3
"""Local GDAL preflight and conversion helper for OpenAerialMap imagery.

This tool never uploads imagery. It runs GDAL locally and prints a concise
JSON diagnostic plus optional, copy/paste-ready GDAL commands.

Examples:
    python validate_imagery.py inspect input.ecw
    python validate_imagery.py validate input.tif
    python validate_imagery.py validate input.tif --json
    python validate_imagery.py convert input.ecw output.tif
    python validate_imagery.py convert input.tif output_cog.tif
    python validate_imagery.py reproject input.tif output_cog.tif --epsg 32751
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


STATUS_ORDER = {"PASS": 0, "WARN": 1, "FAIL": 2}


def fail(message: str, code: int = 1) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return code


def require_command(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(
            f"'{name}' was not found on PATH. Install GDAL and make sure its CLI "
            "tools (gdalinfo/gdal_translate/gdalwarp) are available in this shell."
        )
    return path


def run_gdalinfo(path: Path) -> dict[str, Any]:
    require_command("gdalinfo")
    proc = subprocess.run(
        ["gdalinfo", "-json", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "gdalinfo failed")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gdalinfo returned invalid JSON: {exc}") from exc


def metadata_value(info: dict[str, Any], domain: str, key: str) -> str | None:
    metadata = info.get("metadata") or {}
    values = metadata.get(domain) or {}
    value = values.get(key)
    return str(value) if value is not None else None


def first_band(info: dict[str, Any]) -> dict[str, Any]:
    bands = info.get("bands") or []
    return bands[0] if bands else {}


def band_types(info: dict[str, Any]) -> list[str]:
    return [str(b.get("type", "")) for b in info.get("bands") or []]


def color_interpretations(info: dict[str, Any]) -> list[str]:
    return [str(b.get("colorInterpretation", "")).lower() for b in info.get("bands") or []]


def has_overviews(info: dict[str, Any]) -> bool:
    bands = info.get("bands") or []
    return bool(bands) and all(bool(b.get("overviews")) for b in bands)


def is_tiled(info: dict[str, Any]) -> bool:
    size = info.get("size") or []
    band = first_band(info)
    block = band.get("block") or []
    if len(size) != 2 or len(block) != 2:
        return False
    # A block smaller than the full raster is normally tiled. We deliberately
    # do not require 256x256 or 512x512: COG-compatible block sizes vary.
    return block[0] < size[0] and block[1] < size[1]


def crs_present(info: dict[str, Any]) -> bool:
    cs = info.get("coordinateSystem")
    return bool(cs and (cs.get("wkt") or cs.get("projjson")))


def bounds_summary(info: dict[str, Any]) -> dict[str, Any]:
    corners = info.get("cornerCoordinates") or {}
    return {
        "upperLeft": corners.get("upperLeft"),
        "lowerRight": corners.get("lowerRight"),
        "wgs84Extent": info.get("wgs84Extent"),
    }


def inspect(path: Path) -> dict[str, Any]:
    info = run_gdalinfo(path)
    driver = str(info.get("driverShortName") or info.get("driver", ""))
    bands = info.get("bands") or []
    return {
        "file": str(path.resolve()),
        "extension": path.suffix.lower(),
        "driver": driver,
        "size": info.get("size"),
        "bands": len(bands),
        "bandTypes": band_types(info),
        "colorInterpretations": color_interpretations(info),
        "crsPresent": crs_present(info),
        "isTiled": is_tiled(info),
        "hasOverviews": has_overviews(info),
        "cogLayout": metadata_value(info, "IMAGE_STRUCTURE", "LAYOUT"),
        "compression": metadata_value(info, "IMAGE_STRUCTURE", "COMPRESSION"),
        "bounds": bounds_summary(info),
    }


def add_check(checks: list[dict[str, Any]], status: str, name: str, detail: str) -> None:
    checks.append({"status": status, "name": name, "detail": detail})


def parse_gdalinfo_text(text: str) -> dict[str, Any]:
    """Parse standard plain-text gdalinfo output without requiring JSON."""
    import re

    raw = text.strip()
    if not raw:
        raise ValueError("No gdalinfo output was provided.")

    def search(pattern: str, flags: int = re.MULTILINE):
        return re.search(pattern, raw, flags)

    driver_match = search(r"^Driver:\s*([^/\r\n]+)")
    driver = driver_match.group(1).strip() if driver_match else ""

    size_match = search(r"^Size is\s+(\d+)\s*,\s*(\d+)")
    size = [int(size_match.group(1)), int(size_match.group(2))] if size_match else None

    crs_present_text = bool(search(r"^Coordinate System is:\s*$", re.MULTILINE))
    epsg_match = search(r'ID\["EPSG",\s*(\d+)\]')
    epsg = int(epsg_match.group(1)) if epsg_match else None

    block_matches = re.findall(
        r"^Band\s+(\d+)\s+Block=(\d+)x(\d+)\s+Type=([^,\r\n]+),\s*ColorInterp=([^\r\n]+)",
        raw,
        re.MULTILINE,
    )
    bands: list[dict[str, Any]] = []
    for number, bx, by, dtype, color in block_matches:
        bands.append({
            "band": int(number),
            "block": [int(bx), int(by)],
            "type": dtype.strip(),
            "colorInterpretation": color.strip(),
            "overviews": [],
        })

    # Plain gdalinfo prints overview dimensions on the line after each band.
    # Attach them by walking band sections rather than assuming a fixed count.
    sections = re.split(r"(?=^Band\s+\d+\s+)", raw, flags=re.MULTILINE)[1:]
    for band, section in zip(bands, sections):
        overview_match = re.search(r"^\s*Overviews:\s*(.+)$", section, re.MULTILINE)
        if overview_match:
            band["overviews"] = [x.strip() for x in overview_match.group(1).split(",") if x.strip()]

    wgs_match = search(
        r"^(?:Upper Left|Lower Left|Upper Right|Lower Right)\s+\([^\r\n]+\)"
    )
    has_corners = bool(wgs_match)

    image_structure = "\\n".join(
        f"{key}={value}" for key, value in re.findall(
            r"^\s+(LAYOUT|COMPRESSION)=([^\s\r\n]+)",
            raw,
            re.MULTILINE,
        )
    )
    layout_match = re.search(r"LAYOUT=([^\\s\\r\\n]+)", image_structure)
    compression_match = re.search(r"COMPRESSION=([^\\s\\r\\n]+)", image_structure)

    return {
        "driverShortName": driver,
        "size": size,
        "coordinateSystem": {
            "wkt": "present" if crs_present_text else "",
            "epsg": epsg,
        } if crs_present_text else None,
        "bands": bands,
        "cornerCoordinates": {"present": True} if has_corners else {},
        "wgs84Extent": {"epsg": epsg} if has_corners and epsg == 4326 else ({"present": True} if has_corners and crs_present_text else None),
        "metadata": {
            "IMAGE_STRUCTURE": {
                "LAYOUT": layout_match.group(1) if layout_match else "",
                "COMPRESSION": compression_match.group(1) if compression_match else "",
            }
        },
    }


def validate_info(info: dict[str, Any]) -> dict[str, Any]:
    """Validate already-collected gdalinfo JSON without touching the raster."""
    driver = str(info.get("driverShortName") or info.get("driver", ""))
    bands_data = info.get("bands") or []
    summary = {
        "file": "", "extension": "", "driver": driver, "size": info.get("size"),
        "bands": len(bands_data), "bandTypes": band_types(info),
        "colorInterpretations": color_interpretations(info), "crsPresent": crs_present(info),
        "isTiled": is_tiled(info), "hasOverviews": has_overviews(info),
        "cogLayout": metadata_value(info, "IMAGE_STRUCTURE", "LAYOUT"),
        "compression": metadata_value(info, "IMAGE_STRUCTURE", "COMPRESSION"),
        "bounds": bounds_summary(info),
    }
    checks: list[dict[str, Any]] = []
    d = driver.upper(); ext = ""; bands = summary["bands"]; types = summary["bandTypes"]; colors = summary["colorInterpretations"]
    add_check(checks, "PASS" if d == "GTIFF" else "WARN", "GeoTIFF driver", "GDAL reports GTiff." if d == "GTIFF" else f"GDAL reports {d or 'unknown'}; conversion to GeoTIFF is recommended.")
    add_check(checks, "PASS" if crs_present(info) else "FAIL", "CRS", "A coordinate reference system is present." if crs_present(info) else "No CRS was reported by GDAL.")
    size = info.get("size") or []
    if len(size) == 2 and bands_data:
        width, height = size
        bytes_per_sample = {"BYTE": 1, "UINT8": 1, "INT8": 1, "UINT16": 2, "INT16": 2, "UINT32": 4, "INT32": 4, "FLOAT32": 4, "FLOAT64": 8}
        first_size = bytes_per_sample.get((band_types(info)[0] if band_types(info) else "").upper())
        if first_size:
            decoded_gb = (width * height * len(bands_data) * first_size) / 1e9
            add_check(checks, "PASS" if decoded_gb <= 130 else "FAIL", "OAM decoded size", f"Estimated decoded size is {decoded_gb:.1f} GB (current OAM validation limit: 130 GB)." if decoded_gb <= 130 else f"Estimated decoded size is {decoded_gb:.1f} GB, above the current OAM validation limit of 130 GB.")
        else:
            add_check(checks, "WARN", "OAM decoded size", "Could not estimate decoded size because the pixel type is unknown.")
    else:
        add_check(checks, "WARN", "OAM decoded size", "Could not estimate decoded size from the supplied GDAL output.")
    add_check(checks, "PASS" if bands in (3, 4) else "FAIL", "Band count", f"{bands} bands; suitable for visual RGB/RGBA imagery." if bands in (3,4) else f"Found {bands} bands; visual target expects 3 RGB or 4 RGBA bands.")
    add_check(checks, "PASS" if types and all(t.upper() == "BYTE" for t in types) else "WARN", "Pixel type", "All bands are Byte/uint8." if types and all(t.upper() == "BYTE" for t in types) else f"Band types are {types or 'unknown'}; verify this is visual RGB/RGBA data.")
    rgb_ok = colors[:3] == ["red", "green", "blue"]
    alpha_ok = bands == 4 and len(colors) >= 4 and colors[3] in {"alpha", "undefined"}
    add_check(checks, "PASS" if rgb_ok and (bands == 3 or alpha_ok) else "WARN", "Color interpretation", "Bands are consistent with RGB/RGBA imagery." if rgb_ok and (bands == 3 or alpha_ok) else f"GDAL reports {colors or 'unknown'}; verify the bands.")
    add_check(checks, "PASS" if str(summary["cogLayout"]).upper() == "COG" else "WARN", "COG layout", "GDAL reports IMAGE_STRUCTURE LAYOUT=COG." if str(summary["cogLayout"]).upper() == "COG" else "Not reported as COG; the generated local output can create a COG.")
    add_check(checks, "PASS" if summary["isTiled"] else "WARN", "Internal tiling", "Raster blocks are tiled." if summary["isTiled"] else "Raster is not reported as internally tiled.")
    add_check(checks, "PASS" if summary["hasOverviews"] else "WARN", "Overviews", "All bands contain overviews." if summary["hasOverviews"] else "One or more bands have no reported overviews.")
    add_check(checks, "PASS" if summary["bounds"]["wgs84Extent"] else "WARN", "Geographic extent", "GDAL produced a WGS84 extent." if summary["bounds"]["wgs84Extent"] else "No WGS84 extent was reported; inspect georeferencing.")
    overall = max((STATUS_ORDER[x["status"]] for x in checks), default=2)
    return {"status": {0:"PASS",1:"WARN",2:"FAIL"}[overall], "summary": summary, "checks": checks}
def validate(path: Path) -> dict[str, Any]:
    info = run_gdalinfo(path)
    summary = inspect(path)
    checks: list[dict[str, Any]] = []

    driver = summary["driver"].upper()
    ext = summary["extension"]
    bands = summary["bands"]
    types = summary["bandTypes"]
    colors = summary["colorInterpretations"]

    if driver == "GTIFF":
        add_check(checks, "PASS", "GeoTIFF driver", "GDAL reports GTiff.")
    else:
        add_check(checks, "FAIL", "GeoTIFF driver", f"GDAL reports {driver or 'unknown'}, not GTiff.")

    if ext == ".tif" or ext == ".tiff":
        add_check(checks, "PASS", "File extension", "GeoTIFF extension is present.")
    else:
        add_check(checks, "WARN", "File extension", f"Extension is {ext or 'missing'}; expected .tif/.tiff for the target file.")

    if crs_present(info):
        add_check(checks, "PASS", "CRS", "A coordinate reference system is present.")
    else:
        add_check(checks, "FAIL", "CRS", "No CRS was reported by GDAL.")

    if bands in (3, 4):
        add_check(checks, "PASS", "Band count", f"{bands} bands; suitable for visual RGB/RGBA imagery.")
    else:
        add_check(checks, "FAIL", "Band count", f"Found {bands} bands; visual OAM preflight expects 3 RGB or 4 RGBA bands.")

    if all(t.upper() == "BYTE" for t in types) and types:
        add_check(checks, "PASS", "Pixel type", "All bands are Byte/uint8.")
    else:
        add_check(
            checks,
            "WARN",
            "Pixel type",
            f"Band types are {types or 'unknown'}. Float32/Int16 and other types may be valid for non-visual products, but are not the normal visual RGB/RGBA target.",
        )

    rgb_ok = colors[:3] == ["red", "green", "blue"]
    alpha_ok = bands == 4 and len(colors) >= 4 and colors[3] in {"alpha", "undefined"}
    if rgb_ok and (bands == 3 or alpha_ok):
        add_check(checks, "PASS", "Color interpretation", "Bands are consistent with RGB/RGBA imagery.")
    else:
        add_check(checks, "WARN", "Color interpretation", f"GDAL reports {colors or 'unknown'}; verify the bands are actually RGB/RGBA.")

    if summary["cogLayout"] and summary["cogLayout"].upper() == "COG":
        add_check(checks, "PASS", "COG layout", "GDAL reports IMAGE_STRUCTURE LAYOUT=COG.")
    else:
        add_check(checks, "WARN", "COG layout", "The file is not reported as COG. OAM can convert accepted GeoTIFF input, so this is a readiness warning rather than an OAM hard failure.")

    if summary["isTiled"]:
        add_check(checks, "PASS", "Internal tiling", "Raster blocks are smaller than the full raster dimensions.")
    else:
        add_check(checks, "WARN", "Internal tiling", "GDAL does not report a tiled block layout. This may reduce cloud-optimized performance.")

    if summary["hasOverviews"]:
        add_check(checks, "PASS", "Overviews", "All reported bands contain overviews.")
    else:
        add_check(checks, "WARN", "Overviews", "One or more bands have no reported overviews. A COG conversion can generate them.")

    # Do not reject legitimate imagery merely because a corner happens to be 0,0.
    # Instead, flag missing georeferencing and clearly absent WGS84 extent.
    if summary["bounds"]["wgs84Extent"]:
        add_check(checks, "PASS", "Geographic extent", "GDAL produced a WGS84 extent.")
    else:
        add_check(checks, "WARN", "Geographic extent", "GDAL did not produce a WGS84 extent; inspect georeferencing before upload.")

    overall = max((STATUS_ORDER[c["status"]] for c in checks), default=2)
    status = {0: "PASS", 1: "WARN", 2: "FAIL"}[overall]

    return {"status": status, "summary": summary, "checks": checks}


def quote(path: str) -> str:
    # Double quotes work for normal Windows PowerShell and POSIX shells.
    return '"' + path.replace('"', '\\"') + '"'


def conversion_commands(summary: dict[str, Any], input_path: Path, output_path: Path, epsg: int | None = None) -> dict[str, str]:
    bands = summary.get("bands")
    types = summary.get("bandTypes") or []
    if bands == 4:
        band_args = "-b 1 -b 2 -b 3 -b 4"
        compression = "DEFLATE"
    else:
        band_args = "-b 1 -b 2 -b 3"
        compression = "DEFLATE"

    inp = quote(str(input_path))
    out = quote(str(output_path))

    if epsg:
        warp = f'gdalwarp -t_srs EPSG:{epsg} -of COG -co COMPRESS={compression} {inp} {out}'
        return {"reproject": warp}

    translate = f'gdal_translate -of COG -co COMPRESS={compression} {band_args} {inp} {out}'
    return {"convert": translate}


def build_oam_ready_powershell(input_path: str, output_path: str | None = None, source_epsg: int | None = None) -> str:
    """Build one pasteable PowerShell command; never overwrites the source."""
    src_path = Path(input_path)
    dst = output_path or str(src_path.with_name(src_path.stem + "_oam_ready.tif"))
    if source_epsg:
        return (f'gdalwarp -overwrite -s_srs EPSG:{int(source_epsg)} -of COG '
                f'-co COMPRESS=DEFLATE "{input_path}" "{dst}"')
    return f'gdal_translate -of COG -co COMPRESS=DEFLATE "{input_path}" "{dst}"'

def build_oam_recommendation(info: dict[str, Any], input_path: str, source_epsg: int | None = None, output_path: str | None = None) -> dict[str, Any]:
    """Return a conservative local target for OAM visual RGB/RGBA imagery."""
    bands = len(info.get("bands") or [])
    types = band_types(info)
    issues: list[str] = []
    if bands not in (3, 4):
        issues.append(f"Expected 3 or 4 bands for visual imagery; found {bands}.")
    if types and not all(t.upper() == "BYTE" for t in types):
        issues.append(f"Visual target normally uses Byte/uint8; found {types}.")
    if not crs_present(info) and source_epsg is None:
        issues.append("CRS is missing; supply the correct source EPSG before generating the command.")
    output_path = output_path or str(Path(input_path).with_name(Path(input_path).stem + "_oam_ready.tif"))
    command = None
    if not issues:
        if source_epsg:
            command = (f'gdalwarp -overwrite -s_srs EPSG:{int(source_epsg)} -of COG '
                       f'-co COMPRESS=DEFLATE "{input_path}" "{output_path}"')
        else:
            command = f'gdal_translate -of COG -co COMPRESS=DEFLATE "{input_path}" "{output_path}"'
    return {"ready": not issues, "issues": issues, "output": output_path, "command": command,
            "notes": ["Creates a new file and does not overwrite the source.",
                      "Uses lossless DEFLATE so RGB and RGBA are preserved.",
                      "COG is a local output target; OAM may still perform server-side validation/transcoding."]}
def run_command(command: list[str]) -> int:
    print("$ " + " ".join(quote(c) if " " in c else c for c in command))
    proc = subprocess.run(command)
    return proc.returncode


def print_result(result: dict[str, Any]) -> None:
    print(f"STATUS: {result['status']}")
    for check in result["checks"]:
        print(f"[{check['status']}] {check['name']}: {check['detail']}")


def cmd_inspect(args: argparse.Namespace) -> int:
    path = Path(args.input).expanduser()
    if not path.exists():
        return fail(f"Input does not exist: {path}")
    try:
        result = inspect(path)
    except Exception as exc:
        return fail(str(exc))
    print(json.dumps(result, indent=2 if args.pretty else None))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.input).expanduser()
    if not path.exists():
        return fail(f"Input does not exist: {path}")
    try:
        result = validate(path)
    except Exception as exc:
        return fail(str(exc))

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_result(result)
        print()
        print("Suggested local GDAL action:")
        summary = result["summary"]
        if summary["driver"].upper() != "GTIFF":
            output = path.with_suffix(".tif")
            for label, command in conversion_commands(summary, path, output).items():
                print(f"  {label}: {command}")
        elif result["status"] != "PASS":
            output = path.with_name(path.stem + "_cog.tif")
            for label, command in conversion_commands(summary, path, output).items():
                print(f"  {label}: {command}")
        else:
            print("  No conversion is required by this preflight.")
    return 0 if result["status"] != "FAIL" else 2


def cmd_recommend(args: argparse.Namespace) -> int:
    path = Path(args.input).expanduser()
    if not path.exists():
        return fail(f"Input does not exist: {path}")
    try:
        info = run_gdalinfo(path)
        rec = build_oam_recommendation(info, str(path), args.source_epsg, args.output)
    except Exception as exc:
        return fail(str(exc))
    if args.json:
        print(json.dumps(rec, indent=2))
    else:
        print("OAM VISUAL PREFLIGHT")
        print("STATUS: READY TO CONVERT" if rec["ready"] else "STATUS: INPUT NEEDS ATTENTION")
        for issue in rec["issues"]:
            print(f"- {issue}")
        if rec["ready"]:
            print("\nONE COMBINED POWERSHELL COMMAND:\n" + rec["command"])
            for note in rec["notes"]:
                print(f"- {note}")
        elif args.source_epsg is None and not crs_present(info):
            print(f'\nThen rerun:\npython validate_imagery.py recommend "{path}" --source-epsg <EPSG>')
    return 0 if rec["ready"] else 2

def cmd_convert(args: argparse.Namespace) -> int:
    input_path = Path(args.input).expanduser()
    output_path = Path(args.output).expanduser()
    if not input_path.exists():
        return fail(f"Input does not exist: {input_path}")
    try:
        summary = inspect(input_path)
        require_command("gdal_translate")
        bands = summary["bands"]
        if bands == 4:
            band_args = ["-b", "1", "-b", "2", "-b", "3", "-b", "4"]
            compression = "DEFLATE"
        elif bands == 3:
            band_args = ["-b", "1", "-b", "2", "-b", "3"]
            compression = "DEFLATE"
        else:
            return fail(f"Expected 3 or 4 bands for visual conversion; found {bands}.")

        command = [
            "gdal_translate", "-of", "COG", "-co", f"COMPRESS={compression}",
            *band_args, str(input_path), str(output_path),
        ]
        return run_command(command)
    except Exception as exc:
        return fail(str(exc))


def cmd_reproject(args: argparse.Namespace) -> int:
    input_path = Path(args.input).expanduser()
    output_path = Path(args.output).expanduser()
    if not input_path.exists():
        return fail(f"Input does not exist: {input_path}")
    try:
        summary = inspect(input_path)
        require_command("gdalwarp")
        bands = summary["bands"]
        compression = "DEFLATE"
        command = [
            "gdalwarp", "-t_srs", f"EPSG:{args.epsg}", "-of", "COG",
            "-co", f"COMPRESS={compression}", str(input_path), str(output_path),
        ]
        return run_command(command)
    except Exception as exc:
        return fail(str(exc))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local GDAL preflight helper for OAM visual imagery.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inspect", help="Inspect any GDAL-readable raster, including ECW.")
    p.add_argument("input")
    p.add_argument("--pretty", action="store_true")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("validate", help="Validate a GeoTIFF for visual RGB/RGBA OAM readiness.")
    p.add_argument("input")
    p.add_argument("--json", action="store_true", help="Print machine-readable JSON diagnostics.")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("recommend", help="Inspect a raster and print one pasteable OAM-ready PowerShell command.")
    p.add_argument("input")
    p.add_argument("--source-epsg", type=int, help="Correct source EPSG when input CRS is missing.")
    p.add_argument("--output", help="Output path; defaults to *_oam_ready.tif.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_recommend)

    p = sub.add_parser("convert", help="Convert a 3/4-band raster to a COG locally.")
    p.add_argument("input")
    p.add_argument("output")
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("reproject", help="Reproject a 3/4-band raster directly to a COG.")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--epsg", required=True, type=int, help="Target EPSG code, e.g. 32751.")
    p.set_defaults(func=cmd_reproject)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
