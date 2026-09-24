import unittest

from utils.oam_sources import (
    classify_s3_source_objects,
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


class OAMSourceTests(unittest.TestCase):
    def test_parse_spaceeye_s3_browser_url(self):
        bucket, region, prefix = parse_s3_browser_url(S3_BROWSER)
        self.assertEqual(bucket, "st-vvhr-opendata")
        self.assertEqual(region, "us-west-2")
        self.assertEqual(
            prefix,
            "disasters/Flood in Nepal (Disasters Charter Activation 1052), 2026/",
        )

    def test_filter_tiffs_excludes_qa_artifacts(self):
        objects = [
            {"key": "event/image.tif"},
            {"key": "event/MASKS/image.tif"},
            {"key": "event/LINEAGE/image.tiff"},
            {"key": "event/readme.txt"},
        ]
        self.assertEqual(
            [x["key"] for x in filter_tiff_objects(objects)],
            ["event/image.tif"],
        )
        self.assertEqual(
            [x["key"] for x in filter_tiff_objects(objects, False)],
            [
                "event/image.tif",
                "event/MASKS/image.tif",
                "event/LINEAGE/image.tiff",
            ],
        )

    def test_classify_archive_only_prefix(self):
        objects = [{"key": "event/product.zip"}, {"key": "event/preview.png"}]
        self.assertEqual(classify_s3_source_objects(objects), "ARCHIVE_ONLY")

    def test_classify_direct_raster_prefix(self):
        objects = [{"key": "event/product.zip"}, {"key": "event/product.tif"}]
        self.assertEqual(classify_s3_source_objects(objects), "DIRECT_RASTER")

    def test_classify_empty_prefix(self):
        self.assertEqual(
            classify_s3_source_objects([{"key": "event/readme.txt"}]),
            "EMPTY",
        )

    def test_public_s3_object_url_encodes_object_key(self):
        url = public_s3_object_url(
            "st-vvhr-opendata",
            "us-west-2",
            "disasters/Flood in Nepal, 2026/image (01).tif",
        )
        self.assertEqual(
            url,
            "https://st-vvhr-opendata.s3.us-west-2.amazonaws.com/"
            "disasters/Flood%20in%20Nepal%2C%202026/image%20%2801%29.tif",
        )

    def test_spaceeye_prefill_contains_verified_metadata_and_source_url(self):
        url = spaceeye_oam_prefill(
            key="disasters/example/image.tif",
            object_url=(
                "https://st-vvhr-opendata.s3.us-west-2.amazonaws.com/"
                "disasters/example/image.tif"
            ),
            source_browser_url=S3_BROWSER,
        )
        self.assertTrue(url.startswith("https://upload.imagery.hotosm.org/#"))
        self.assertIn("provider=SI%20Imaging%20Services", url)
        self.assertIn("platform=satellite", url)
        self.assertIn("sensor=SpaceEye-T", url)
        self.assertIn("license=CC-BY%204.0", url)
        self.assertIn(
            "source_url=https%3A%2F%2Fst-vvhr-opendata.s3.us-west-2.amazonaws.com%2F",
            url,
        )
        self.assertNotIn("acquisition_start=", url)
        self.assertNotIn("acquisition_end=", url)

    def test_generic_prefill_does_not_invent_missing_metadata(self):
        url = build_oam_prefill_url(
            title="Example",
            source_url="https://example.org/image.tif",
        )
        self.assertIn("title=Example", url)
        self.assertIn(
            "source_url=https%3A%2F%2Fexample.org%2Fimage.tif",
            url,
        )
        self.assertNotIn("license=", url)
        self.assertNotIn("acquisition_start=", url)


if __name__ == "__main__":
    unittest.main()
