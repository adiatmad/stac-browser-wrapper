import unittest

from validate_imagery import build_oam_recommendation, parse_gdalinfo_text, validate_info


ECW_GDALINFO = r"""Driver: ECW/ERDAS Compressed Wavelets (SDK 5.5)
Size is 26482, 25891
Coordinate System is:
GEOGCRS["WGS 84",
ID["EPSG",4326]]
Origin = (120.123611111111003,-8.412092845769511)
Pixel Size = (0.000000356402000,-0.000000356402000)
Corner Coordinates:
Upper Left  ( 120.1236111,  -8.4120928)
Lower Left  ( 120.1236111,  -8.4213204)
Upper Right ( 120.1330493,  -8.4120928)
Lower Right ( 120.1330493, -8.4213204)
Band 1 Block=256x256 Type=Byte, ColorInterp=Undefined
  Overviews: 13241x12945, 6620x6472, 3310x3236, 1655x1618, 827x809, 413x404, 206x202
Band 2 Block=256x256 Type=Byte, ColorInterp=Undefined
  Overviews: 13241x12945, 6620x6472, 3310x3236, 1655x1618, 827x809, 413x404, 206x202
Band 3 Block=256x256 Type=Byte, ColorInterp=Undefined
  Overviews: 13241x12945, 6620x6472, 3310x3236, 1655x1618, 827x809, 413x404, 206x202
Band 4 Block=256x256 Type=Byte, ColorInterp=Undefined
  Overviews: 13241x12945, 6620x6472, 3310x3236, 1655x1618, 827x809, 413x404, 206x202
"""


class OAMPreflightTests(unittest.TestCase):
    def test_plain_gdalinfo_parses_real_ecw_shape(self):
        info = parse_gdalinfo_text(ECW_GDALINFO)
        self.assertTrue(info["driverShortName"].startswith("ECW"))
        self.assertEqual(info["size"], [26482, 25891])
        self.assertEqual(len(info["bands"]), 4)
        self.assertTrue(all(b["type"] == "Byte" for b in info["bands"]))
        self.assertEqual(info["coordinateSystem"]["epsg"], 4326)
        self.assertTrue(info["wgs84Extent"])
        self.assertEqual(len(info["bands"][0]["overviews"]), 7)

    def test_visual_ecw_has_no_hard_oam_failure(self):
        info = parse_gdalinfo_text(ECW_GDALINFO)
        result = validate_info(info)
        self.assertFalse([c for c in result["checks"] if c["status"] == "FAIL"])
        size_check = next(c for c in result["checks"] if c["name"] == "OAM decoded size")
        self.assertIn("GB", size_check["detail"])

    def test_undefined_color_interpretation_remains_a_warning(self):
        info = parse_gdalinfo_text(ECW_GDALINFO)
        result = validate_info(info)
        color_check = next(c for c in result["checks"] if c["name"] == "Color interpretation")
        self.assertEqual(color_check["status"], "WARN")
        self.assertIn("undefined", color_check["detail"].lower())

    def test_plain_gdalinfo_parses_generated_cog_metadata(self):
        cog = ECW_GDALINFO + r"""
Image Structure Metadata:
  COMPRESSION=DEFLATE
  INTERLEAVE=PIXEL
  LAYOUT=COG
"""
        info = parse_gdalinfo_text(cog)
        self.assertEqual(info["metadata"]["IMAGE_STRUCTURE"]["LAYOUT"], "COG")
        self.assertEqual(info["metadata"]["IMAGE_STRUCTURE"]["COMPRESSION"], "DEFLATE")
        result = validate_info(info)
        cog_check = next(c for c in result["checks"] if c["name"] == "COG layout")
        self.assertEqual(cog_check["status"], "PASS")

    def test_color_warning_does_not_recommend_reconversion(self):
        info = parse_gdalinfo_text(ECW_GDALINFO + r"""
Image Structure Metadata:
  COMPRESSION=DEFLATE
  INTERLEAVE=PIXEL
  LAYOUT=COG
""")
        result = validate_info(info)
        self.assertEqual(result["status"], "WARN")
        rec = build_oam_recommendation(info, r"C:\\drone\\orthomosaic.tif")
        self.assertTrue(rec["ready"])
        self.assertIsNotNone(rec["command"])

    def test_ecw_gets_local_cog_command_without_uploading(self):
        info = parse_gdalinfo_text(ECW_GDALINFO)
        rec = build_oam_recommendation(info, r"C:\drone\orthomosaic.ecw")
        self.assertTrue(rec["ready"])
        self.assertIn("gdal_translate -of COG", rec["command"])
        self.assertIn("COMPRESS=DEFLATE", rec["command"])
        self.assertIn(r"C:\drone\orthomosaic_oam_ready.tif", rec["command"])
        self.assertNotIn("gdalwarp", rec["command"])


if __name__ == "__main__":
    unittest.main()
