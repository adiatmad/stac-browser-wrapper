from pathlib import Path
import ast
import math
import re
import unittest
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]


def load_helpers():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="app.py")
    wanted = {
        "parse_stac_catalog_registry",
        "filter_public_stac_catalogs",
        "find_stac_search_endpoint",
        "build_stac_search_url",
        "find_stac_thumbnail_url",
        "resolve_relative_url",
        "crawl_stac",
    }
    body = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted
    ]
    namespace = {
        "Any": object,
        "math": math,
        "urlsplit": urlsplit,
        "urlunsplit": urlunsplit,
        "parse_qsl": parse_qsl,
        "urlencode": urlencode,
        "urljoin": urljoin,
        "re": re,
        "fetch_json": lambda *_: None,
        "process_item_data": lambda *_: None,
        "st": type("FakeStreamlit", (), {"warning": staticmethod(lambda *_: None)}),
    }
    exec(compile(ast.Module(body=body, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace


class STACDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = load_helpers()

    def test_registry_keeps_only_public_https_records(self):
        records = [
            {"title": "Public API", "url": "https://example.org/stac", "access": "public", "isPrivate": False, "isApi": True},
            {"title": "Protected", "url": "https://private.example.org", "access": "protected", "isPrivate": True},
            {"title": "Private flag mismatch", "url": "https://hidden.example.org", "access": "public", "isPrivate": True},
            {"title": "HTTP endpoint", "url": "http://insecure.example.org", "access": "public", "isPrivate": False},
            {"title": "Missing URL", "access": "public", "isPrivate": False},
        ]
        result = self.helpers["parse_stac_catalog_registry"](records)
        self.assertEqual([item["title"] for item in result], ["Public API"])
        self.assertTrue(result[0]["is_api"])

    def test_registry_rejects_non_list_payload(self):
        with self.assertRaisesRegex(ValueError, "JSON list"):
            self.helpers["parse_stac_catalog_registry"]({"catalogs": []})
        malformed_url = [{"title": "Bad", "url": "https://[invalid", "access": "public", "isPrivate": False}]
        self.assertEqual(self.helpers["parse_stac_catalog_registry"](malformed_url), [])

    def test_catalog_filter_searches_title_and_summary_case_insensitively(self):
        records = [
            {"title": "Copernicus", "summary": "Satellite imagery"},
            {"title": "Local data", "summary": "Sentinel and Landsat coverage"},
        ]
        result = self.helpers["filter_public_stac_catalogs"](records, "sentinel")
        self.assertEqual([item["title"] for item in result], ["Local data"])

    def test_search_endpoint_uses_advertised_get_link(self):
        root = {
            "links": [
                {"rel": "search", "href": "/search", "method": "GET"},
            ]
        }
        self.assertEqual(
            self.helpers["find_stac_search_endpoint"]("https://data.example.org/v1/", root),
            "https://data.example.org/search",
        )

    def test_search_endpoint_rejects_post_only_or_missing_link(self):
        root = {"links": [{"rel": "search", "href": "/search", "method": "POST"}]}
        with self.assertRaisesRegex(ValueError, "POST-only"):
            self.helpers["find_stac_search_endpoint"]("https://data.example.org/", root)
        with self.assertRaises(ValueError):
            self.helpers["find_stac_search_endpoint"]("https://data.example.org/", {"links": []})
        malformed = {"links": [{"rel": "search", "href": "https://[invalid", "method": "GET"}]}
        with self.assertRaises(ValueError):
            self.helpers["find_stac_search_endpoint"]("https://data.example.org/", malformed)

    def test_search_url_encodes_core_filters_and_preserves_existing_query(self):
        result = self.helpers["build_stac_search_url"](
            "https://data.example.org/search?token=abc",
            bbox="106.6,-6.5,107.1,-6.0",
            datetime_range="2026-01-01/2026-03-31",
            collections="sentinel-2-l2a, landsat-c2-l2",
            limit=75,
        )
        parsed = urlsplit(result)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "data.example.org")
        params = dict(parse_qsl(parsed.query))
        self.assertEqual(params["token"], "abc")
        self.assertEqual(params["bbox"], "106.6,-6.5,107.1,-6.0")
        self.assertEqual(params["datetime"], "2026-01-01/2026-03-31")
        self.assertEqual(params["collections"], "sentinel-2-l2a,landsat-c2-l2")
        self.assertEqual(params["limit"], "75")

    def test_search_url_rejects_invalid_bbox_and_limit(self):
        build = self.helpers["build_stac_search_url"]
        for bbox in ("1,2,3", "1,2,3,4,5", "181,-1,182,1", "10,5,10,8", "10,8,20,5", "nan,0,1,1"):
            with self.subTest(bbox=bbox), self.assertRaises(ValueError):
                build("https://data.example.org/search", bbox=bbox)
        dateline = build("https://data.example.org/search", bbox="170,-10,-170,10")
        self.assertIn("bbox=170%2C-10%2C-170%2C10", dateline)
        for limit in (0, 1001, "not-a-number"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                build("https://data.example.org/search", limit=limit)


    def test_crawler_stops_after_item_cap_without_fetching_next_page(self):
        crawl = self.helpers["crawl_stac"]
        processed = []

        def process_item_data(item_url, feature, tiff_links, oam_items):
            processed.append(feature["id"])

        self.helpers["process_item_data"] = process_item_data
        all_links, tiff_links, oam_items = [], [], []
        state = {"pages": 0, "capped": False, "post_next": False}
        crawl(
            "https://data.example.org/search",
            all_links,
            tiff_links,
            oam_items,
            max_items=2,
            max_pages=5,
            crawl_state=state,
            data={
                "type": "FeatureCollection",
                "features": [
                    {"id": "one", "links": [{"rel": "self", "href": "/items/one"}]},
                    {"id": "two", "links": [{"rel": "self", "href": "/items/two"}]},
                    {"id": "three", "links": [{"rel": "self", "href": "/items/three"}]},
                ],
                "links": [{"rel": "next", "href": "/search?page=2", "method": "GET"}],
            },
        )
        self.assertEqual(processed, ["one", "two"])
        self.assertEqual(len(all_links), 2)
        self.assertTrue(state["capped"])

    def test_crawler_stops_at_page_cap_and_rejects_post_pagination(self):
        crawl = self.helpers["crawl_stac"]
        processed = []

        def process_item_data(item_url, feature, tiff_links, oam_items):
            processed.append(feature["id"])

        self.helpers["process_item_data"] = process_item_data
        all_links, tiff_links, oam_items = [], [], []
        page_state = {"pages": 0, "capped": False, "post_next": False}
        crawl(
            "https://data.example.org/search",
            all_links,
            tiff_links,
            oam_items,
            max_items=10,
            max_pages=1,
            crawl_state=page_state,
            data={
                "type": "FeatureCollection",
                "features": [{"id": "one"}],
                "links": [{"rel": "next", "href": "/search?page=2", "method": "GET"}],
            },
        )
        self.assertEqual(processed, ["one"])
        self.assertTrue(page_state["capped"])

        post_state = {"pages": 0, "capped": False, "post_next": False}
        crawl(
            "https://data.example.org/post-search",
            [],
            [],
            [],
            max_items=10,
            max_pages=5,
            crawl_state=post_state,
            data={
                "type": "FeatureCollection",
                "features": [{"id": "two"}],
                "links": [{"rel": "next", "href": "/post-search?page=2", "method": "POST"}],
            },
        )
        self.assertTrue(post_state["post_next"])

    def test_thumbnail_requires_explicit_thumbnail_role_and_https_image(self):
        helper = self.helpers["find_stac_thumbnail_url"]
        item_url = "https://data.example.org/items/scene.json"
        item = {
            "assets": {
                "visual": {"href": "https://data.example.org/scene.tif", "roles": ["data"], "type": "image/tiff"},
                "preview": {"href": "../preview.jpg", "roles": ["thumbnail"], "type": "image/jpeg"},
            }
        }
        self.assertEqual(helper(item, item_url), "https://data.example.org/preview.jpg")
        self.assertIsNone(helper({"assets": {"preview": {"href": "http://bad.example.org/a.jpg", "roles": ["thumbnail"]}}}, item_url))
        self.assertIsNone(helper({"assets": {"visual": {"href": "https://data.example.org/a.jpg", "roles": ["data"]}}}, item_url))
        malformed = {"assets": {"thumbnail": {"href": "https://[invalid", "roles": ["thumbnail"], "type": "image/jpeg"}}}
        self.assertIsNone(helper(malformed, item_url))


if __name__ == "__main__":
    unittest.main()
