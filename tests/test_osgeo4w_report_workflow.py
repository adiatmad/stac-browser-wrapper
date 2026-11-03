from __future__ import annotations

import ast
import json
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

    def test_osgeo4w_commands_use_the_pasted_windows_path_and_clip_report(self):
        commands = self.helpers["build_osgeo4w_commands"](r"D:\imagery folder\orthomosaic.tif")
        self.assertEqual(commands["version"], "gdalinfo --version")
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

    def test_oam_upload_size_is_a_hard_limit_but_prebuilt_cog_is_not_required(self):
        info = self.sample_info()
        too_large = self.helpers["validate_local_oam_raster"](
            info, "visual", 101 * 1024**3
        )
        upload_check = next(
            item for item in too_large["checks"] if item["name"] == "Source file size"
        )
        self.assertEqual(upload_check["status"], "FAIL")
        self.assertIn("OAM will reject", upload_check["detail"])

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
        self.assertNotIn("source_url", fields)
        self.assertNotIn("gsd", fields)
        self.assertNotIn("product_type", fields)
        self.assertNotIn("D:", url)


if __name__ == "__main__":
    unittest.main()
