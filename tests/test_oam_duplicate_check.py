import ast
import unittest
from pathlib import Path
from urllib.parse import urljoin, urlsplit


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
APP_TREE = ast.parse(APP_SOURCE, filename="app.py")


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class FakeRequests:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("Unexpected extra OAM request")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def load_duplicate_checker(fake_requests, overlap=0.0):
    wanted = {
        "generate_oam_map_link",
        "_fetch_oam_duplicate_features",
        "check_oam_duplicate",
    }
    nodes = [
        node for node in APP_TREE.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    namespace = {
        "requests": fake_requests,
        "HOTOSM_STAC_ITEMS_API": (
            "https://api.imagery.hotosm.org/stac/collections/openaerialmap/items"
        ),
        "urljoin": urljoin,
        "urlsplit": urlsplit,
        "parse_bbox_2d": lambda bbox: bbox[:4] if bbox and len(bbox) >= 4 else None,
        "calculate_exact_iou": lambda _geometry, bbox: overlap if bbox == [9, 9, 9, 9] else 0.0,
    }
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), "app.py", "exec"),
        namespace,
    )
    return namespace["check_oam_duplicate"]


def page(features=None, next_href=None, method=None):
    links = []
    if next_href:
        link = {"rel": "next", "href": next_href}
        if method:
            link["method"] = method
        links.append(link)
    return FakeResponse({"type": "FeatureCollection", "features": features or [], "links": links})


class OAMDuplicateCheckTests(unittest.TestCase):
    def meta(self, provider_item_id="scene-12"):
        return {
            "provider_item_id": provider_item_id,
            "bbox": [100.0, -5.0, 101.0, -4.0],
            "geometry": None,
        }

    def test_exact_item_id_matches(self):
        requests = FakeRequests([page([{"id": "scene-12", "properties": {"title": "Other title"}}])])
        result = load_duplicate_checker(requests)(self.meta())

        self.assertTrue(result["exists"])
        self.assertEqual(result["oam_id"], "scene-12")
        self.assertEqual(result["status_str"], "Already exists (Exact ID match)")
        self.assertEqual(result["pages_checked"], 1)
        self.assertFalse(requests.calls[0][1]["allow_redirects"])

    def test_title_substring_is_not_an_identifier_match(self):
        requests = FakeRequests([
            page([{"id": "unrelated-item", "properties": {"title": "Old scene-12 imagery"}}])
        ])
        result = load_duplicate_checker(requests)(self.meta())

        self.assertFalse(result["exists"])
        self.assertIn("Not found", result["status_str"])

    def test_follows_next_page_and_finds_exact_id_beyond_first_page(self):
        requests = FakeRequests([
            page([{"id": "other-item"}], "?cursor=second"),
            page([{"id": "scene-12"}]),
        ])
        result = load_duplicate_checker(requests)(self.meta())

        self.assertTrue(result["exists"])
        self.assertEqual(result["pages_checked"], 2)
        self.assertEqual(len(requests.calls), 2)
        self.assertEqual(requests.calls[0][1]["params"], {"bbox": "100.0,-5.0,101.0,-4.0", "limit": 100})
        self.assertIsNone(requests.calls[1][1]["params"])

    def test_spatial_duplicate_is_checked_on_later_pages(self):
        requests = FakeRequests([
            page([{"id": "first-item"}], "?cursor=second"),
            page([{"id": "spatial-match", "bbox": [9, 9, 9, 9]}]),
        ])
        result = load_duplicate_checker(requests, overlap=0.8)(self.meta())

        self.assertTrue(result["exists"])
        self.assertEqual(result["oam_id"], "spatial-match")
        self.assertIn("Spatial Overlap 80%", result["status_str"])

    def test_page_cap_is_inconclusive_not_ready_for_submission(self):
        responses = [
            page([{"id": f"item-{index}"}], f"?cursor={index + 1}")
            for index in range(10)
        ]
        requests = FakeRequests(responses)
        result = load_duplicate_checker(requests)(self.meta())

        self.assertFalse(result["exists"])
        self.assertTrue(result["status_str"].startswith("Inconclusive"))
        self.assertEqual(result["pages_checked"], 10)
        self.assertEqual(len(requests.calls), 10)

    def test_item_cap_applies_if_server_ignores_requested_page_size(self):
        requests = FakeRequests([page([{"id": f"item-{index}"} for index in range(1001)])])
        result = load_duplicate_checker(requests)(self.meta())

        self.assertFalse(result["exists"])
        self.assertTrue(result["status_str"].startswith("Inconclusive"))
        self.assertEqual(result["pages_checked"], 1)
        self.assertEqual(len(requests.calls), 1)

    def test_rejects_next_link_to_another_host(self):
        requests = FakeRequests([page([], "https://attacker.example/collect")])
        result = load_duplicate_checker(requests)(self.meta())

        self.assertFalse(result["exists"])
        self.assertIn("Check Failed", result["status_str"])
        self.assertEqual(len(requests.calls), 1)

    def test_rejects_non_get_pagination(self):
        requests = FakeRequests([page([], "?cursor=second", method="POST")])
        result = load_duplicate_checker(requests)(self.meta())

        self.assertFalse(result["exists"])
        self.assertIn("unsupported non-GET", result["status_str"])
        self.assertEqual(len(requests.calls), 1)

    def test_rejects_repeated_next_link(self):
        requests = FakeRequests([
            page([], "?cursor=repeat"),
            page([], "?cursor=repeat"),
        ])
        result = load_duplicate_checker(requests)(self.meta())

        self.assertFalse(result["exists"])
        self.assertIn("repeated next link", result["status_str"])
        self.assertEqual(len(requests.calls), 2)

    def test_missing_bbox_is_not_reported_as_not_found(self):
        requests = FakeRequests([])
        result = load_duplicate_checker(requests)({"provider_item_id": "scene-12"})

        self.assertFalse(result["exists"])
        self.assertTrue(result["status_str"].startswith("Unable to check"))
        self.assertEqual(len(requests.calls), 0)


if __name__ == "__main__":
    unittest.main()
