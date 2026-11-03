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

    def test_local_raster_workflow_uses_one_path(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("Local raster path", source)
        self.assertIn("gdalinfo -json", source)
        self.assertIn("build_osgeo4w_commands(source_value)", source)
        self.assertIn('st.form("oam_gdal_report_form"', source)
        self.assertIn('st.form_submit_button("Analyse GDAL report", type="primary")', source)
        self.assertIn("never opens your D: drive or receives raster bytes.", source)
        self.assertIn("Review the report for sensitive file paths or metadata before pasting.", source)
        self.assertIn("100 GiB OAM uploader ceiling", source)
        self.assertIn("OAM creates its own COG", source)
        self.assertIn("build_oam_local_prefill_url(metadata)", source)
        self.assertNotIn("Separate DroneTM task-download and mosaic workflow", source)
        self.assertNotIn("https://github.com/adiatmad/dronetm-progress-mosaic", source)
        self.assertNotIn("api.drone.hotosm.org", source)
        self.assertNotRegex(source, r"requests\.(post|put|patch|delete)\s*\(")

    def test_generated_cog_commands_refuse_to_overwrite_existing_outputs(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("gdalwarp -overwrite", source)
        self.assertNotIn("Remove-Item $out -Force", source)
        self.assertIn("Test-Path -LiteralPath $out", source)
        self.assertIn("Output already exists; choose a different output path.", source)

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
        inline_recommendation = namespace["build_oam_recommendation"](parsed_inline, "input.tif")
        original_recommendation = original_recommend(parsed_original, "input.tif")
        for field in ("ready", "issues", "output", "notes"):
            self.assertEqual(inline_recommendation[field], original_recommendation[field])
        self.assertIn("gdal_translate -of COG -co COMPRESS=DEFLATE", inline_recommendation["command"])
        self.assertIn('"input.tif" "$out"', inline_recommendation["command"])
        self.assertIn("Test-Path -LiteralPath $out", inline_recommendation["command"])
        self.assertNotIn("-overwrite", inline_recommendation["command"])

    def test_inlined_oam_helpers_match_existing_module(self):
        import re
        from urllib.parse import quote, unquote, urlencode, urlsplit
        import xml.etree.ElementTree as ET
        import utils.oam_sources as original

        source = (ROOT / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="app.py")
        wanted = {
            "parse_s3_browser_url", "classify_s3_source_objects", "filter_tiff_objects",
            "public_s3_object_url", "build_remote_vsizip_path",
            "spaceeye_verified_archive_member", "build_archive_proxy_url",
            "format_bytes", "build_oam_prefill_url", "spaceeye_oam_prefill",
        }
        constants = {
            "OAM_UPLOAD_URL", "SPACE_EYE_LICENSE", "SPACE_EYE_PROVIDER",
            "SPACE_EYE_PLATFORM", "SPACE_EYE_SENSOR",
            "SPACE_EYE_VERIFIED_ARCHIVE_KEY", "SPACE_EYE_VERIFIED_ARCHIVE_MEMBER",
            "SPACE_EYE_VERIFIED_TIFF_DATETIME", "_S3_WEBSITE_RE",
        }
        body = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted:
                body.append(node)
            elif isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id in constants
                for target in node.targets
            ):
                body.append(node)
        namespace = {
            "re": re, "quote": quote, "unquote": unquote,
            "urlencode": urlencode, "urlsplit": urlsplit, "ET": ET,
        }
        exec(compile(ast.Module(body=body, type_ignores=[]), "app.py", "exec"), namespace)

        examples = [
            ("parse_s3_browser_url", ("https://example-bucket.s3-website-us-west-2.amazonaws.com/#prefix=imagery%2F",), {}),
            ("classify_s3_source_objects", ([{"key": "imagery/scene.tif"}],), {}),
            ("filter_tiff_objects", ([{"key": "imagery/scene.tif"}, {"key": "imagery/MASKS/mask.tif"}],), {}),
            ("public_s3_object_url", ("example-bucket", "us-west-2", "imagery/scene one.tif"), {}),
            ("build_remote_vsizip_path", ("https://example.org/archive.zip", "scene/image.tif"), {}),
            ("spaceeye_verified_archive_member", (original.SPACE_EYE_VERIFIED_ARCHIVE_KEY,), {}),
            ("build_archive_proxy_url", ("https://proxy.example.org", "https://example.org/a.zip", "scene/a.tif"), {}),
            ("format_bytes", (1536,), {}),
            ("build_oam_prefill_url", (), {"title": "Sample", "source_url": "https://example.org/a.tif", "license": "CC-BY 4.0"}),
            ("spaceeye_oam_prefill", (), {"key": "sample.tif", "object_url": "https://example.org/sample.tif", "source_browser_url": "https://example.org/"}),
        ]
        for name, args, kwargs in examples:
            with self.subTest(helper=name):
                self.assertEqual(namespace[name](*args, **kwargs), getattr(original, name)(*args, **kwargs))

    def test_shadcn_ui_dependencies_and_components_are_declared(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        ast.parse(source, filename="app.py")
        self.assertIn("import streamlit_shadcn_ui as ui", source)
        self.assertIn("ui.badge(", source)
        self.assertIn("ui.metric_card(", source)
        self.assertRegex(requirements, r"(?m)^streamlit>=1\.60\.0$")
        self.assertRegex(requirements, r"(?m)^streamlit-shadcn-ui>=1\.4\.0,<2\.0\.0$")

    def test_ui_refresh_preserves_imagery_and_publication_safeguards(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("Check OAM v2 for Duplicates", source)
        self.assertIn("Prepare OAM v2 upload", source)
        self.assertIn("Apply filter", source)
        self.assertIn("This app does not upload the file", source)
        self.assertNotRegex(source, r"requests\.(post|put|patch|delete)\s*\(")

    def test_hallmark_workbench_navigation_and_accessibility_shell(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        ast.parse(source, filename="app.py")
        self.assertIn('st.title("STAC Imagery Workbench")', source)
        self.assertIn('active_workflow = ui.tabs(', source)
        self.assertIn('options=["Discover & map", "Local preparation"]', source)
        self.assertIn('variant="line"', source)
        self.assertIn('key="active-workflow-tabs"', source)
        for existing_key in (
            "preflight_path",
            "source_mode",
            "location_filter_map",
        ):
            self.assertIn(f'key="{existing_key}"', source)
        self.assertNotIn('st.segmented_control(', source)
        self.assertIn('if active_workflow == "Local preparation":', source)
        self.assertIn('elif active_workflow == "Discover & map":', source)
        self.assertIn('with st.spinner("Discovering STAC items and imagery assets..."):', source)
        self.assertIn('No STAC imagery links were found.', source)
        self.assertIn('No OAM-compatible STAC items are available', source)
        self.assertIn('st.header("Choose an imagery source")', source)
        self.assertIn('st.header("Local geospatial imagery preparation")', source)
        self.assertIn('key="preflight_path"', source)
        self.assertIn('st.form_submit_button("Analyse GDAL report", type="primary")', source)
        self.assertIn('gdalinfo -json', source)
        self.assertNotIn('st.form_submit_button("Inspect raster", type="primary")', source)
        self.assertNotIn('Inspect raster with GDAL', source)
        self.assertNotIn('GDAL bin directory (optional)', source)
        self.assertNotIn('Separate DroneTM task-download and mosaic workflow', source)
        self.assertNotIn("<style>", source)
        self.assertNotIn("--app-canvas:", source)
        self.assertIn("No file is uploaded by this workbench", source)
