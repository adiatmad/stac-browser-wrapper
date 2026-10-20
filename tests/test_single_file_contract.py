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
