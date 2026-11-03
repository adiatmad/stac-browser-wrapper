from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app.py"
FUNCTIONS = {
    "resolve_local_gdal_tools",
    "run_local_gdalinfo",
    "_local_decoded_bytes",
    "validate_local_oam_raster",
    "create_local_thumbnail",
    "build_local_cog",
    "_geojson_positions",
    "build_local_oam_item",
    "write_local_oam_item",
    "build_oam_local_prefill_url",
}
CONSTANTS = {
    "OAM_STAC_SCHEMA_URL",
    "OAM_SUPPORTED_PRODUCTS",
    "OAM_SUPPORTED_LICENSES",
    "OAM_MAX_UPLOAD_BYTES",
    "OAM_UPLOAD_URL",
}


def load_helpers():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename="app.py")
    body = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in FUNCTIONS:
            body.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in CONSTANTS
            for target in node.targets
        ):
            body.append(node)
    namespace = {
        "Any": Any,
        "Path": Path,
        "datetime": datetime,
        "os": os,
        "json": json,
        "re": __import__("re"),
        "shutil": shutil,
        "subprocess": subprocess,
        "quote": quote,
        "urlencode": urlencode,
    }
    exec(compile(ast.Module(body=body, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


class LocalImageryWorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = load_helpers()

    def sample_info(self, *, dtype="Byte", count=3, colors=None):
        colors = colors or ["Red", "Green", "Blue"][:count]
        return {
            "driverShortName": "GTiff",
            "size": [100, 80],
            "geoTransform": [106.9, 0.000001, 0, -6.2, 0, -0.000001],
            "coordinateSystem": {"wkt": "WGS 84", "id": {"authority": "EPSG", "code": 4326}},
            "wgs84Extent": {
                "type": "Polygon",
                "coordinates": [[[106.9, -6.2], [107.0, -6.2], [107.0, -6.3], [106.9, -6.3], [106.9, -6.2]]],
            },
            "metadata": {"IMAGE_STRUCTURE": {"LAYOUT": "COG", "COMPRESSION": "DEFLATE"}},
            "bands": [
                {"band": i + 1, "type": dtype, "colorInterpretation": colors[i] if i < len(colors) else "Undefined", "block": [512, 512], "overviews": [{"size": [50, 40]}]}
                for i in range(count)
            ],
        }

    def test_resolves_gdal_tools_from_explicit_bin_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            suffix = ".exe" if os.name == "nt" else ""
            for name in ("gdalinfo", "gdal_translate"):
                (root / f"{name}{suffix}").write_text("", encoding="utf-8")
            found = self.helpers["resolve_local_gdal_tools"](str(root))
            self.assertEqual(Path(found["gdalinfo"]).parent, root)
            self.assertEqual(Path(found["gdal_translate"]).parent, root)

    def test_gdalinfo_uses_argument_list_and_parses_json(self):
        with tempfile.TemporaryDirectory() as temp:
            raster = Path(temp) / "source.tif"
            raster.write_bytes(b"test")
            payload = json.dumps(self.sample_info())
            with mock.patch.object(
                self.helpers["subprocess"],
                "run",
                return_value=subprocess.CompletedProcess([], 0, payload, ""),
            ) as run:
                info = self.helpers["run_local_gdalinfo"](str(raster), {"gdalinfo": "gdalinfo"})
            self.assertEqual(info["size"], [100, 80])
            args = run.call_args.args[0]
            self.assertEqual(args[:2], ["gdalinfo", "-json"])
            self.assertNotIn("shell", run.call_args.kwargs)

    def test_product_aware_validation_does_not_force_nonvisual_data_to_byte_rgb(self):
        info = self.sample_info(dtype="Float32", count=1, colors=["Gray"])
        elevation = self.helpers["validate_local_oam_raster"](info, "elevation", 1024)
        visual = self.helpers["validate_local_oam_raster"](info, "visual", 1024)
        self.assertFalse(any(item["status"] == "FAIL" for item in elevation["checks"]))
        visual_failure = next(item for item in visual["checks"] if item["name"] == "Visual pixel contract")
        self.assertEqual(visual_failure["status"], "FAIL")

    def test_missing_crs_is_a_hard_failure(self):
        info = self.sample_info()
        info["coordinateSystem"] = {}
        result = self.helpers["validate_local_oam_raster"](info, "visual", 1024)
        crs_check = next(item for item in result["checks"] if item["name"] == "Coordinate reference system")
        self.assertEqual(crs_check["status"], "FAIL")

    def test_upload_size_ceiling_is_reported(self):
        info = self.sample_info()
        result = self.helpers["validate_local_oam_raster"](info, "visual", 101 * 1024**3)
        upload_check = next(item for item in result["checks"] if item["name"] == "Upload file size")
        self.assertEqual(upload_check["status"], "FAIL")

    def test_cog_creation_preserves_source_and_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.tif"
            output = root / "prepared.tif"
            source.write_bytes(b"original")
            output.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                self.helpers["build_local_cog"](
                    str(source), str(output), self.sample_info(), "visual",
                    {"gdalinfo": "gdalinfo", "gdal_translate": "gdal_translate"},
                )
            self.assertEqual(source.read_bytes(), b"original")
            self.assertEqual(output.read_bytes(), b"existing")

    def test_cog_creation_uses_lossless_cog_driver_and_verifies_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.tif"
            output = root / "prepared.tif"
            source.write_bytes(b"original")
            info = self.sample_info()
            helpers = self.helpers
            original_run_gdalinfo = helpers["run_local_gdalinfo"]
            original_thumbnail = helpers["create_local_thumbnail"]

            def fake_run(args, **kwargs):
                Path(args[-1]).write_bytes(b"cog")
                return subprocess.CompletedProcess(args, 0, "", "")

            helpers["run_local_gdalinfo"] = lambda path, tools: self.sample_info()
            helpers["create_local_thumbnail"] = lambda *args: None
            try:
                with mock.patch.object(helpers["subprocess"], "run", side_effect=fake_run) as run:
                    result = helpers["build_local_cog"](
                        str(source), str(output), info, "visual",
                        {"gdalinfo": "gdalinfo", "gdal_translate": "gdal_translate"},
                    )
                command = run.call_args.args[0]
                self.assertIn("-of", command)
                self.assertIn("COG", command)
                self.assertIn("COMPRESS=DEFLATE", command)
                self.assertNotIn("-overwrite", command)
                self.assertTrue(output.is_file())
                self.assertEqual(source.read_bytes(), b"original")
                self.assertEqual(result["path"], str(output.resolve()))
            finally:
                helpers["run_local_gdalinfo"] = original_run_gdalinfo
                helpers["create_local_thumbnail"] = original_thumbnail

    def test_stac_item_uses_gdal_extent_and_user_metadata(self):
        metadata = {
            "title": "Jakarta orthomosaic",
            "producer": "Example mapping team",
            "platform": "uav",
            "product_type": "visual",
            "gsd": 0.05,
            "datetime": "2026-11-03T02:03:04+07:00",
            "license": "CC-BY-4.0",
            "sensor": "Example camera",
        }
        item = self.helpers["build_local_oam_item"](
            self.sample_info(), r"D:\imagery\prepared.tif", metadata,
            r"D:\imagery\prepared_thumbnail.png",
        )
        self.assertEqual(item["bbox"], [106.9, -6.3, 107.0, -6.2])
        self.assertEqual(item["geometry"]["type"], "Polygon")
        self.assertEqual(item["assets"]["visual"]["href"], "./prepared.tif")
        self.assertEqual(item["assets"]["thumbnail"]["href"], "./prepared_thumbnail.png")
        self.assertEqual(item["properties"]["datetime"], "2026-11-03T02:03:04+07:00")
        self.assertEqual(item["properties"]["oam:product_type"], "visual")

    def test_stac_item_rejects_missing_extent_or_timezone(self):
        info = self.sample_info()
        info.pop("wgs84Extent")
        metadata = {
            "title": "T", "producer": "P", "platform": "uav", "product_type": "visual",
            "gsd": 0.05, "datetime": "2026-11-03T02:03:04", "license": "CC-BY-4.0",
        }
        with self.assertRaisesRegex(ValueError, "WGS84 extent"):
            self.helpers["build_local_oam_item"](info, "image.tif", metadata)
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.helpers["build_local_oam_item"](self.sample_info(), "image.tif", metadata)

    def test_nonvisual_thumbnail_is_not_fabricated_as_rgb(self):
        info = self.sample_info(dtype="Float32", count=1, colors=["Gray"])
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "elevation.tif"
            source.write_bytes(b"source")
            result = self.helpers["create_local_thumbnail"](
                str(source), info, "elevation", {"gdal_translate": "gdal_translate"}
            )
        self.assertIsNone(result)

    def test_metadata_writer_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "item.json"
            output.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                self.helpers["write_local_oam_item"]({"type": "Feature"}, str(output))
            self.assertEqual(output.read_text(encoding="utf-8"), "keep")

    def test_oam_prefill_never_contains_local_path_or_source_url(self):
        url = self.helpers["build_oam_local_prefill_url"]({
            "title": "Jakarta orthomosaic",
            "producer": "Example team",
            "platform": "uav",
            "license": "CC-BY-4.0",
            "datetime": "2026-11-03T02:03:04Z",
            "sensor": "Camera X",
            "product_type": "visual",
            "local_path": r"D:\imagery\prepared.tif",
        })
        fragment = url.split("#", 1)[1]
        self.assertIn("title=Jakarta", fragment)
        self.assertIn("product_type=visual", fragment)
        self.assertNotIn("source_url", fragment)
        self.assertNotIn("D%3A", fragment)
        self.assertNotIn("imagery", fragment)


if __name__ == "__main__":
    unittest.main()
