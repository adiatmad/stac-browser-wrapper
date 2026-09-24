from utils.oam_sources import (
    filter_tiff_objects,
    build_oam_prefill_url,
    parse_s3_browser_url,
    public_s3_object_url,
    spaceeye_oam_prefill,
)


S3_BROWSER = (
    "http://st-vvhr-opendata.s3-website.us-west-2.amazonaws.com/"
    "#prefix=disasters%2FFlood%20in%20Nepal%20(Disasters%20Charter%20Activation%201052)%2C%202026%2F"
)


def test_parse_spaceeye_s3_browser_url():
    bucket, region, prefix = parse_s3_browser_url(S3_BROWSER)
    assert bucket == "st-vvhr-opendata"
    assert region == "us-west-2"
    assert prefix == "disasters/Flood in Nepal (Disasters Charter Activation 1052), 2026/"


def test_filter_tiffs_excludes_qa_artifacts():
    objects = [
        {"key": "event/image.tif"},
        {"key": "event/MASKS/image.tif"},
        {"key": "event/LINEAGE/image.tiff"},
        {"key": "event/readme.txt"},
    ]
    assert [x["key"] for x in filter_tiff_objects(objects)] == ["event/image.tif"]
    assert [x["key"] for x in filter_tiff_objects(objects, False)] == [
        "event/image.tif",
        "event/MASKS/image.tif",
        "event/LINEAGE/image.tiff",
    ]


def test_public_s3_object_url_encodes_object_key():
    url = public_s3_object_url(
        "st-vvhr-opendata",
        "us-west-2",
        "disasters/Flood in Nepal, 2026/image (01).tif",
    )
    assert url == (
        "https://st-vvhr-opendata.s3.us-west-2.amazonaws.com/"
        "disasters/Flood%20in%20Nepal%2C%202026/image%20%2801%29.tif"
    )


def test_spaceeye_prefill_contains_verified_metadata_and_source_url():
    url = spaceeye_oam_prefill(
        key="disasters/example/image.tif",
        object_url="https://st-vvhr-opendata.s3.us-west-2.amazonaws.com/disasters/example/image.tif",
        source_browser_url=S3_BROWSER,
    )
    assert url.startswith("https://upload.imagery.hotosm.org/#")
    assert "provider=SI%20Imaging%20Services" in url
    assert "platform=Satellite" in url
    assert "sensor=SpaceEye-T" in url
    assert "license=CC-BY%204.0" in url
    assert "source_url=https%3A%2F%2Fst-vvhr-opendata.s3.us-west-2.amazonaws.com%2F" in url
    assert "acquisition_start=" not in url
    assert "acquisition_end=" not in url


def test_generic_prefill_does_not_invent_missing_metadata():
    url = build_oam_prefill_url(
        title="Example",
        source_url="https://example.org/image.tif",
    )
    assert "title=Example" in url
    assert "source_url=https%3A%2F%2Fexample.org%2Fimage.tif" in url
    assert "license=" not in url
    assert "acquisition_start=" not in url
