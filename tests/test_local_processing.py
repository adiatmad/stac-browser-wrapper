import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import local_processing as lp

class LocalProcessingTests(unittest.TestCase):
    def test_command_is_lossless_zstd_geotiff(self):
        joined = " ".join(lp.compression_command("gdal_translate", "source.tif", "out.tif", predictor=2))
        for opt in ("COMPRESS=ZSTD", "ZSTD_LEVEL=9", "PREDICTOR=2", "BLOCKXSIZE=512", "BLOCKYSIZE=512", "BIGTIFF=YES", "NUM_THREADS=ALL_CPUS"):
            self.assertIn(opt, joined)
        self.assertNotIn("JPEG", joined)
        self.assertNotIn("-scale", joined)
        self.assertNotIn("-outsize", joined)

    def test_gdal_failure_includes_stderr_diagnostic(self):
        import subprocess
        with patch("local_processing.subprocess.run", side_effect=subprocess.CalledProcessError(1, ["gdal_translate"], stderr="ZSTD codec unavailable")):
            with self.assertRaisesRegex(RuntimeError, "ZSTD codec unavailable"):
                lp._run(["gdal_translate", "source.tif", "out.tif"])

    def test_structural_validation_passes_matching_tiled_geotiff(self):
        src = {"size": [10, 20], "geoTransform": [0, 1, 0, 20, 0, -1], "coordinateSystem": {"id": {"authority": "EPSG", "code": "4326"}}, "bands": [{"type": "Byte", "colorInterpretation": "Red", "noDataValue": 0}]}
        out = {**src, "metadata": {"IMAGE_STRUCTURE": {"COMPRESSION": "ZSTD"}}, "bands": [{"block": [512, 512], **src["bands"][0]}]}
        self.assertEqual(lp._compare_raster_structure(src, out), [])

    def test_validation_detects_structure_and_compression_issues(self):
        src = {"size": [10, 20], "geoTransform": [0, 1, 0, 20, 0, -1], "bands": []}
        out = {"size": [11, 20], "geoTransform": [0, 1, 0, 20, 0, -1], "bands": [], "metadata": {"IMAGE_STRUCTURE": {"COMPRESSION": "DEFLATE"}}, "bands": [{"block": [20, 10]}]}
        issues = lp._compare_raster_structure(src, out)
        self.assertTrue(any("dimensions" in x for x in issues))
        self.assertTrue(any("ZSTD" in x for x in issues))

    def test_existing_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            src, out = Path(td)/"src.tif", Path(td)/"out.tif"
            src.write_bytes(b"source"); out.write_bytes(b"preserve")
            with patch.object(lp, "_run") as mocked:
                with self.assertRaisesRegex(ValueError, "already exists"):
                    lp.process_lossless_geotiff("gdalinfo", "gdal_translate", str(src), str(out), False)
                mocked.assert_not_called()
            self.assertEqual(out.read_bytes(), b"preserve")

    def test_missing_crs_or_geotransform_is_rejected_before_conversion(self):
        with tempfile.TemporaryDirectory() as td:
            src, out = Path(td)/"src.tif", Path(td)/"out.tif"
            src.write_bytes(b"source")
            with patch.object(lp, "read_raster_info", return_value={"size": [1, 1], "bands": [{"type": "Byte"}]}):
                with patch.object(lp, "_run") as mocked:
                    with self.assertRaisesRegex(ValueError, "missing a CRS"):
                        lp.process_lossless_cog("gdalinfo", "gdal_translate", str(src), str(out), False)
                    mocked.assert_not_called()

    def test_source_output_same_path_refused(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td)/"src.tif"; src.write_bytes(b"source")
            with self.assertRaisesRegex(ValueError, "different output"):
                lp.process_lossless_cog("gdalinfo", "gdal_translate", str(src), str(src), False)

if __name__ == "__main__":
    unittest.main()
