from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app.py"


class ReportDrivenLocalImageryWorkflowTests(unittest.TestCase):
    def test_local_processing_runs_gdal_on_local_orthomosaic(self):
        source = SOURCE.read_text(encoding="utf-8")
        helpers = (ROOT / "local_processing.py").read_text(encoding="utf-8")
        ast.parse(source, filename="app.py")
        ast.parse(helpers, filename="local_processing.py")

        self.assertIn('options=["Discover & map", "Local processing"]', source)
        self.assertIn("find_gdal_tools()", source)
        self.assertIn("process_lossless_cog(", source)
        self.assertIn("gdalinfo -json", helpers)
        self.assertIn("COMPRESS=ZSTD", helpers)
        self.assertIn("LEVEL=12", helpers)
        self.assertIn("PREDICTOR=YES", helpers)
        self.assertIn("OVERVIEW_RESAMPLING=AVERAGE", helpers)
        self.assertIn("source.resolve() == output.resolve()", helpers)
        self.assertIn("output.exists()", helpers)
        self.assertIn("checksum", helpers)
        self.assertNotIn("JPEG", helpers)

    def test_oam_handoff_opens_uploader_without_a_separate_metadata_form(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('st.link_button("Open official OAM uploader", OAM_UPLOAD_URL)', source)
        self.assertIn('Open official OAM uploader', source)
        self.assertNotIn("local_oam_metadata_form", source)
        self.assertNotIn("build_oam_local_prefill_url", source)

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
