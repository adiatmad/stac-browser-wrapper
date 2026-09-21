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
  Overviews: 13241x12945, 6620x6472, 3310x3236
Band 2 Block=256x256 Type=Byte, ColorInterp=Undefined
  Overviews: 13241x12945, 6620x6472, 3310x3236
Band 3 Block=256x256 Type=Byte, ColorInterp=Undefined
  Overviews: 13241x12945, 6620x6472, 3310x3236
Band 4 Block=256x256 Type=Byte, ColorInterp=Undefined
  Overviews: 13241x12945, 6620x6472, 3310x3236
"""


def test_plain_gdalinfo_parses_visual_ecw():
    info = parse_gdalinfo_text(ECW_GDALINFO)
    assert info["driverShortName"].startswith("ECW")
    assert info["size"] == [26482, 25891]
    assert len(info["bands"]) == 4
    assert all(b["type"] == "Byte" for b in info["bands"])
    assert info["coordinateSystem"]["epsg"] == 4326
    assert info["wgs84Extent"]


def test_visual_ecw_has_no_hard_oam_failure():
    info = parse_gdalinfo_text(ECW_GDALINFO)
    result = validate_info(info)
    assert not [c for c in result["checks"] if c["status"] == "FAIL"]


def test_ecw_gets_local_cog_command_without_uploading():
    info = parse_gdalinfo_text(ECW_GDALINFO)
    rec = build_oam_recommendation(
        info,
        r"C:\drone\orthomosaic.ecw",
    )
    assert rec["ready"] is True
    assert "gdal_translate -of COG" in rec["command"]
    assert "COMPRESS=DEFLATE" in rec["command"]
    assert r"C:\drone\orthomosaic_oam_ready.tif" in rec["command"]
