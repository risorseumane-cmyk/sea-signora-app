import importlib
import os
import tempfile
import unittest


class TestParsingAndEmail(unittest.TestCase):
    def _load_app_module(self):
        if "backend.app" in globals():
            del globals()["backend.app"]
        import backend.app as app_module
        return importlib.reload(app_module)

    def test_qty_unit_parsing_and_conversion(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["APP_DB_PATH"] = os.path.join(td, "test.db")
            app_module = self._load_app_module()

            qty, unit, cleaned = app_module.extract_qty_and_unit("500g di broccoli")
            self.assertEqual(qty, 500.0)
            self.assertEqual(unit, "g")
            self.assertIn("broccoli", cleaned)

            converted = app_module.convert_qty(500.0, "g", "kg")
            self.assertAlmostEqual(converted, 0.5, places=6)

    def test_local_smart_parse_converts_to_product_um(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["APP_DB_PATH"] = os.path.join(td, "test.db")
            app_module = self._load_app_module()

            products = [
                {"id": 1, "name": "Broccoli", "cat": "Ortofrutta", "um": "kg", "prices": {"A": 2.0}},
            ]
            parsed = app_module.local_smart_parse("500g broccoli", products)
            self.assertEqual(len(parsed["items"]), 1)
            item = parsed["items"][0]
            self.assertEqual(item["productId"], 1)
            self.assertEqual(item["um"], "kg")
            self.assertAlmostEqual(item["qty"], 0.5, places=6)

    def test_local_smart_parse_unmatched_suggestions(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["APP_DB_PATH"] = os.path.join(td, "test.db")
            app_module = self._load_app_module()

            products = [
                {"id": 1, "name": "Broccoli", "cat": "Ortofrutta", "um": "kg", "prices": {"A": 2.0}},
                {"id": 2, "name": "Briciole Pane", "cat": "Forno", "um": "kg", "prices": {"A": 3.0}},
            ]
            parsed = app_module.local_smart_parse("bxl", products)
            self.assertEqual(len(parsed["items"]), 0)
            self.assertEqual(len(parsed["unmatched"]), 1)
            sug = parsed["unmatched"][0]["suggestions"]
            self.assertTrue(any(s["name"] == "Broccoli" for s in sug))

    def test_public_base_url_from_forwarded_headers(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["APP_DB_PATH"] = os.path.join(td, "test.db")
            app_module = self._load_app_module()

            with app_module.app.test_request_context(
                "/api/order",
                headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "example.com"},
            ):
                base = app_module.get_public_base_url(app_module.request)
                self.assertEqual(base, "https://example.com")


if __name__ == "__main__":
    unittest.main()
