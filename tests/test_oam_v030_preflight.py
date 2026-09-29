import unittest

from utils.oam_v030_preflight import OAM_SCHEMA_URL, check_oam_item


class OAMV030PreflightTests(unittest.TestCase):
    def valid_item(self):
        return {
            "type": "Feature",
            "stac_extensions": [OAM_SCHEMA_URL],
            "geometry": {"type": "Polygon", "coordinates": [[[120, -9], [120.1, -9], [120.1, -8.9], [120, -8.9], [120, -9]]]},
            "bbox": [120, -9, 120.1, -8.9],
            "gsd": 0.05,
            "providers": [{"name": "Example Drone Team", "roles": ["producer", "licensor"]}],
            "properties": {
                "title": "Example UAV orthomosaic",
                "datetime": "2026-09-29T01:00:00Z",
                "license": "CC-BY-4.0",
                "oam:platform_type": "uav",
                "oam:producer_name": "Example Drone Team",
                "oam:product_type": "visual",
            },
            "assets": {"visual": {"href": "https://example.org/image.tif", "roles": ["visual"]}},
        }

    def test_current_minimum_contract_passes(self):
        result = check_oam_item(self.valid_item())
        self.assertEqual(result["status"], "PASS")

    def test_missing_required_metadata_is_reported_individually(self):
        item = self.valid_item()
        item["properties"].pop("oam:producer_name")
        item["properties"].pop("title")
        item["gsd"] = None
        result = check_oam_item(item)
        failed = {c["name"] for c in result["checks"] if c["status"] == "FAIL"}
        self.assertTrue({"GSD", "Producer", "Title"}.issubset(failed))

    def test_elevation_is_not_called_a_visual_failure(self):
        item = self.valid_item()
        item["properties"]["oam:product_type"] = "elevation"
        result = check_oam_item(item)
        product_check = next(c for c in result["checks"] if c["name"] == "Product type")
        self.assertEqual(product_check["status"], "PASS")

    def test_wrong_license_is_explicit(self):
        item = self.valid_item()
        item["properties"]["license"] = "proprietary"
        result = check_oam_item(item)
        license_check = next(c for c in result["checks"] if c["name"] == "License")
        self.assertEqual(license_check["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
