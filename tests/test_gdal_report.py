import unittest

from utils.gdal_report import parse_detailed_gdalinfo, visual_assessment


REPORT = r"""Driver: GTiff/GeoTIFF
Size is 49018, 15082
Coordinate System is:
GEOGCRS["WGS 84",
    ID["EPSG",4326]]
Origin = (-100.371095377000003,20.604583195000000)
Pixel Size = (0.000000475663430,-0.000000455389670)
Metadata:
  AREA_OR_POINT=Area
Image Structure Metadata:
  INTERLEAVE=PIXEL
Corner Coordinates:
Upper Left  (-100.3710954,  20.6045832)
Lower Left  (-100.3710954,  20.5977150)
Upper Right (-100.3477793,  20.6045832)
Lower Right (-100.3477793,  20.5977150)
Center      (-100.3594373,  20.6011491)
Band 1 Block=49018x1 Type=Float32, ColorInterp=Gray
  NoData Value=-3.4028235e+38
Band 2 Block=49018x1 Type=Float32, ColorInterp=Undefined
  NoData Value=-3.4028235e+38
Band 3 Block=49018x1 Type=Float32, ColorInterp=Undefined
  NoData Value=-3.4028235e+38
Band 4 Block=49018x1 Type=Float32, ColorInterp=Undefined
  NoData Value=-3.4028235e+38
"""


class DetailedGDALReportTests(unittest.TestCase):
    def test_extracts_raster_facts(self):
        report = parse_detailed_gdalinfo(REPORT)
        self.assertEqual(report["driver"], "GTiff/GeoTIFF")
        self.assertEqual(report["size"], [49018, 15082])
        self.assertEqual(report["epsg"], 4326)
        self.assertEqual(report["origin"], [-100.371095377, 20.604583195])
        self.assertEqual(len(report["bands"]), 4)
        self.assertEqual(report["bands"][0]["type"], "Float32")
        self.assertEqual(report["bands"][0]["nodata"], "-3.4028235e+38")
        self.assertEqual(report["bands"][0]["block"], [49018, 1])

    def test_decoded_size_is_reported(self):
        report = parse_detailed_gdalinfo(REPORT)
        self.assertIsNotNone(report["decodedBytes"])
        self.assertGreater(report["decodedBytes"], 0)

    def test_float32_four_band_report_is_not_visual_candidate(self):
        assessment = visual_assessment(parse_detailed_gdalinfo(REPORT))
        self.assertEqual(assessment["status"], "FAIL")
        self.assertIn("Float32", assessment["detail"])

    def test_rgb_byte_report_is_visual_candidate(self):
        rgb = REPORT.replace("Float32", "Byte").replace("Gray", "Red")
        rgb = rgb.replace("Band 2 Block=49018x1 Type=Byte, ColorInterp=Undefined", "Band 2 Block=49018x1 Type=Byte, ColorInterp=Green")
        rgb = rgb.replace("Band 3 Block=49018x1 Type=Byte, ColorInterp=Undefined", "Band 3 Block=49018x1 Type=Byte, ColorInterp=Blue")
        rgb = rgb.replace("Band 4 Block=49018x1 Type=Byte, ColorInterp=Undefined\n  NoData Value=-3.4028235e+38\n", "")
        assessment = visual_assessment(parse_detailed_gdalinfo(rgb))
        self.assertEqual(assessment["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
