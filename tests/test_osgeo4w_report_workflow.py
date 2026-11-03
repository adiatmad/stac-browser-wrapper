from __future__ import annotations

import ast
import json
import math
import ntpath
import re
import unittest
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app.py"
FUNCTIONS = {
    "_local_decoded_bytes",
    "_normalise_windows_path",
    "gdal_report_matches_path",
    "has_usable_geotransform",
    "validate_local_oam_raster",
    "parse_oam_gdalinfo_report",
    "suggest_oam_product_type",
    "build_osgeo4w_commands",
    "build_oam_cog_command",
    "build_osgeo4w_verify_commands",
    "build_oam_local_prefill_url",
}
CONSTANTS = {
    "OAM_MAX_UPLOAD_BYTES",
    "OAM_SUPPORTED_PRODUCTS",
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
        "json": json,
        "math": math,
        "re": re,
        "ntpath": ntpath,
        "urlencode": urlencode,
        "quote": quote,
    }
    exec(compile(ast.Module(body=body, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


class OSGeo4WReportWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = load_helpers()

    def sample_info(self, *, driver="GTiff", dtype="Byte", count=3, colors=None):
        colors = colors or ["Red", "Green", "Blue"][:count]
        return {
            "description": r"D:\imagery folder\orthomosaic.tif",
            "files": [r"D:\imagery folder\orthomosaic.tif"],
            "driverShortName": driver,
            "size": [1000, 500],
            "geoTransform": [106.9, 0.00001, 0, -6.2, 0, -0.00001],
            "coordinateSystem": {
                "wkt": "WGS 84",
                "id": {"authority": "EPSG", "code": 4326},
            },
            "metadata": {"IMAGE_STRUCTURE": {"COMPRESSION": "DEFLATE"}},
            "bands": [
                {
                    "band": index + 1,
                    "type": dtype,
                    "colorInterpretation": colors[index] if index < len(colors) else "Undefined",
                    "block": [512, 512],
                    "overviews": [],
                }
                for index in range(count)
            ],
        }

    def test_json_report_is_parsed_and_incomplete_report_is_rejected(self):
        info = self.sample_info()
        parsed = self.helpers["parse_oam_gdalinfo_report"](json.dumps(info))
        self.assertEqual(parsed["size"], [1000, 500])
        with self.assertRaisesRegex(ValueError, "GDAL JSON report is incomplete"):
            self.helpers["parse_oam_gdalinfo_report"]('{"driverShortName":"GTiff"}')
 
    def test_report_must_match_the_path_and_warns_when_gdal_omits_it(self):
        info = self.sample_info()
        matches = self.helpers["gdal_report_matches_path"]
        self.assertIs(matches(info, r"D:\imagery folder\orthomosaic.tif"), True)
        self.assertIs(matches(info, r"D:\other\orthomosaic.tif"), False)
        info.pop("description")
        info.pop("files")
        self.assertIsNone(matches(info, r"D:\imagery folder\orthomosaic.tif"))

    def test_osgeo4w_path_must_be_absolute(self):
        with self.assertRaisesRegex(ValueError, "full absolute Windows path"):
            self.helpers["build_osgeo4w_commands"]("orthomosaic.tif")

    def test_affine_geotransform_is_required_for_reliable_oam_metadata(self):
        has_transform = self.helpers["has_usable_geotransform"]
        info = self.sample_info()
        self.assertTrue(has_transform(info))
        tiny_pixels = self.sample_info()
        tiny_pixels["geoTransform"] = [0, 1e-9, 0, 0, 0, -1e-9]
        self.assertTrue(has_transform(tiny_pixels))
        info["geoTransform"] = [0, 0, 0, 0, 0, 0]
        self.assertFalse(has_transform(info))
        info.pop("geoTransform")
        self.assertFalse(has_transform(info))
        result = self.helpers["validate_local_oam_raster"](info, "visual", 1024)
        georeferencing = next(item for item in result["checks"] if item["name"] == "Affine georeferencing")
        self.assertEqual(georeferencing["status"], "FAIL")

        identity = self.sample_info()
        identity["geoTransform"] = [0, 1, 0, 0, 0, 1]
        result = self.helpers["validate_local_oam_raster"](identity, "visual", 1024)
        georeferencing = next(item for item in result["checks"] if item["name"] == "Affine georeferencing")
        self.assertEqual(georeferencing["status"], "WARN")

    def test_oam_decoded_size_uses_the_first_band_dtype_like_upstream(self):
        info = self.sample_info()
        info["bands"][1]["type"] = "Float32"
        self.assertEqual(self.helpers["_local_decoded_bytes"](info), 1000 * 500 * 3)

    def test_crs_identifier_alone_counts_as_a_declared_crs(self):
        info = self.sample_info()
        info["coordinateSystem"] = {"id": {"authority": "EPSG", "code": 4326}}
        result = self.helpers["validate_local_oam_raster"](info, "visual", 1024)
        crs_check = next(item for item in result["checks"] if item["name"] == "Coordinate reference system")
        self.assertEqual(crs_check["status"], "PASS")

    def test_osgeo4w_commands_use_the_pasted_windows_path_and_clip_report(self):
        commands = self.helpers["build_osgeo4w_commands"](r"D:\imagery folder\orthomosaic.tif")
        self.assertEqual(commands["version"], "gdalinfo --version")
        self.assertEqual(commands["cog_driver"], "gdalinfo --format COG")
        self.assertEqual(
            commands["report"],
            r'gdalinfo -json "D:\imagery folder\orthomosaic.tif" | clip',
        )
        self.assertIn("Get-Item -LiteralPath 'D:\\imagery folder\\orthomosaic.tif'", commands["size"])
        self.assertIn(".Length", commands["size"])

    def test_product_suggestion_matches_oam_metadata_detection_without_guessing_fourth_band_alpha(self):
        visual = self.sample_info()
        self.assertEqual(self.helpers["suggest_oam_product_type"](visual), "visual")

        elevation = self.sample_info(dtype="Float32", count=1, colors=["Gray"])
        self.assertEqual(self.helpers["suggest_oam_product_type"](elevation), "elevation")

        ambiguous_four_band = self.sample_info(count=4, colors=["Red", "Green", "Blue", "Undefined"])
        self.assertEqual(self.helpers["suggest_oam_product_type"](ambiguous_four_band), "multispectral")

    def test_declared_visual_with_undefined_fourth_band_gets_a_warning(self):
        info = self.sample_info(count=4)
        result = self.helpers["validate_local_oam_raster"](info, "visual", 1024)
        fourth_band = next(
            item for item in result["checks"] if item["name"] == "Fourth band"
        )
        self.assertEqual(fourth_band["status"], "WARN")
        self.assertIn("JPEG conversion path only treats band 4 as alpha", fourth_band["detail"])

    def test_cog_command_is_non_overwriting_and_assigns_only_an_explicit_epsg(self):
        build = self.helpers["build_oam_cog_command"]
        command = build(r"D:\scene.ecw", r"D:\scene_oam_ready.tif")
        self.assertIn("if exist", command)
        self.assertIn("else (gdal_translate -of COG", command)
        self.assertIn(r'"D:\scene.ecw" "D:\scene_oam_ready.tif"', command)
        self.assertNotIn("-a_srs", command)
        self.assertNotIn("-overwrite", command)

        assigned = build(r"D:\scene.ecw", r"D:\scene_oam_ready.tif", "32751")
        self.assertIn("-a_srs EPSG:32751", assigned)
        with self.assertRaisesRegex(ValueError, "differ from the source"):
            build(r"D:\scene.tif", r"d:\SCENE.tif")
        with self.assertRaisesRegex(ValueError, "numeric EPSG"):
            build(r"D:\scene.ecw", r"D:\scene_oam_ready.tif", "EPSG:4326")

    def test_oam_default_upload_ceiling_and_optional_cog_requirement(self):
        info = self.sample_info()
        too_large = self.helpers["validate_local_oam_raster"](
            info, "visual", 101 * 1024**3
        )
        upload_check = next(
            item for item in too_large["checks"] if item["name"] == "Source file size"
        )
        self.assertEqual(upload_check["status"], "FAIL")
        self.assertIn("deployed service may override", upload_check["detail"])

        no_size = self.helpers["validate_local_oam_raster"](info, "visual")
        upload_check = next(
            item for item in no_size["checks"] if item["name"] == "Source file size"
        )
        self.assertEqual(upload_check["status"], "WARN")

        cog_check = next(
            item for item in no_size["checks"] if item["name"] == "Cloud Optimized GeoTIFF"
        )
        self.assertEqual(cog_check["status"], "INFO")
        self.assertIn("not required", cog_check["detail"])

    def test_uploader_prefill_uses_supported_fields_and_matching_license_display_values(self):
        url = self.helpers["build_oam_local_prefill_url"](
            {
                "title": "Metinaro orthomosaic",
                "producer": "KFF",
                "platform": "uav",
                "license": "CC-BY-4.0",
                "acquisition_start": "2026-11-03",
                "acquisition_end": "2026-11-04",
                "contact": "team@example.org",
                "product_type": "",
            }
        )
        parsed = urlsplit(url)
        fields = parse_qs(parsed.fragment)
        self.assertEqual(fields["title"], ["Metinaro orthomosaic"])
        self.assertEqual(fields["provider"], ["KFF"])
        self.assertEqual(fields["license"], ["CC-BY 4.0"])
        self.assertEqual(fields["acquisition_start"], ["2026-11-03"])
        self.assertEqual(fields["acquisition_end"], ["2026-11-04"])
        self.assertNotIn("source_url", fields)
        self.assertNotIn("gsd", fields)
        self.assertNotIn("product_type", fields)
        self.assertNotIn("D:", url)


if __name__ == "__main__":
    unittest.main()
