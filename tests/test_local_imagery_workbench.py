from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app.py"


class ReportDrivenLocalImageryWorkflowTests(unittest.TestCase):
    def test_local_preparation_generates_commands_without_executing_local_gdal(self):
        source = SOURCE.read_text(encoding="utf-8")
        ast.parse(source, filename="app.py")

        self.assertIn("build_osgeo4w_commands(source_value)", source)
        self.assertIn("gdalinfo -json", source)
        self.assertIn('"report_file": f"gdalinfo -json {quoted} > {report_path}"', source)
        self.assertIn('"copy_report": f"clip < {report_path}"', source)
        self.assertIn('"open_report": f"notepad {report_path}"', source)
        self.assertNotIn('gdalinfo -json {quoted} | clip', source)
        self.assertIn("parse_oam_gdalinfo_report(report_text)", source)
        self.assertIn("gdal_report_matches_path(info, source_value)", source)
        self.assertIn("has_usable_geotransform(info)", source)

    def test_oam_handoff_opens_uploader_without_a_separate_metadata_form(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('st.link_button("Open official OAM uploader", OAM_UPLOAD_URL)', source)
        self.assertIn('st.markdown("### 7 · Open the OAM uploader")', source)
        self.assertNotIn("local_oam_metadata_form", source)
        self.assertNotIn("build_oam_local_prefill_url", source)

        # The hosted app must never try to inspect a user's local filesystem.
        self.assertNotIn("subprocess.run(", source)
        self.assertNotIn("run_local_gdalinfo", source)
        self.assertNotIn("resolve_local_gdal_tools", source)
        self.assertNotIn("Path(source_value)", source)
        self.assertNotIn("source_value.is_file()", source)

    def test_superseded_local_cog_and_stac_sidecar_helpers_are_not_runtime_code(self):
        source = SOURCE.read_text(encoding="utf-8")
        for legacy_helper in (
            "build_local_cog",
            "create_local_thumbnail",
            "build_local_oam_item",
            "write_local_oam_item",
        ):
            with self.subTest(helper=legacy_helper):
                self.assertNotIn(legacy_helper, source)


if __name__ == "__main__":
    unittest.main()
