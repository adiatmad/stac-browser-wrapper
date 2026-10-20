from pathlib import Path
import ast
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HostedSingleFileContractTests(unittest.TestCase):
    def test_app_has_no_project_specific_python_imports(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        ast.parse(source, filename="app.py")
        self.assertNotIn("from validate_imagery import", source)
        self.assertNotIn("from utils.oam_sources import", source)
        self.assertNotIn("from mosaic_core import", source)

    def test_drone_workflow_is_explicitly_local(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("run on your computer", source)
        self.assertIn("https://github.com/adiatmad/dronetm-progress-mosaic", source)
        self.assertIn("cannot read your Windows folders or run OSGeo4W", source)

    def test_inlined_validation_helpers_match_existing_module(self):
        import re
        from typing import Any
        from validate_imagery import (
            parse_gdalinfo_text as original_parse,
            validate_info as original_validate,
            build_oam_recommendation as original_recommend,
        )

        source = (ROOT / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="app.py")
        wanted = {
            "metadata_value", "first_band", "band_types", "color_interpretations",
            "has_overviews", "is_tiled", "crs_present", "bounds_summary",
            "add_check", "parse_gdalinfo_text", "validate_info",
            "build_oam_recommendation",
        }
        body = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted:
                body.append(node)
            elif isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "STATUS_ORDER"
                for target in node.targets
            ):
                body.append(node)
        namespace = {"re": re, "Any": Any, "Path": __import__("pathlib").Path}
        exec(compile(ast.Module(body=body, type_ignores=[]), "app.py", "exec"), namespace)

        gdal_text = """Driver: GTiff/GeoTIFF
Size is 20, 10
Coordinate System is:
GEOGCRS["WGS 84",
    ID["EPSG",4326]]
Origin = (1.0,2.0)
Pixel Size = (0.1,-0.1)
Corner Coordinates:
Upper Left (1.0,2.0)
Lower Right (3.0,1.0)
Band 1 Block=20x10 Type=Byte, ColorInterp=Red
Band 2 Block=20x10 Type=Byte, ColorInterp=Green
Band 3 Block=20x10 Type=Byte, ColorInterp=Blue
"""
        parsed_inline = namespace["parse_gdalinfo_text"](gdal_text)
        parsed_original = original_parse(gdal_text)
        self.assertEqual(parsed_inline, parsed_original)
        self.assertEqual(namespace["validate_info"](parsed_inline), original_validate(parsed_original))
        self.assertEqual(
            namespace["build_oam_recommendation"](parsed_inline, "input.tif"),
            original_recommend(parsed_original, "input.tif"),
        )
