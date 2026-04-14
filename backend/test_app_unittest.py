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

    def test_ai_weights_validation_and_audit(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["APP_DB_PATH"] = os.path.join(td, "test.db")
            app_module = self._load_app_module()
            client = app_module.app.test_client()

            bad = {"settings": {"aiWeights": {"price": 80, "porto": 10}}}
            r = client.post("/api/admin/page-settings", json=bad)
            self.assertEqual(r.status_code, 400)

            good = {"settings": {"aiWeights": {"price": 70, "porto": 30}}}
            r2 = client.post("/api/admin/page-settings", json=good)
            self.assertEqual(r2.status_code, 200)
            self.assertTrue(r2.get_json().get("ok"))

            audit = client.get("/api/admin/ai-audit").get_json()
            self.assertTrue(audit.get("ok"))
            self.assertTrue(len(audit.get("audit", [])) >= 1)

    def test_state_save_guard_refuses_empty_catalog(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["APP_DB_PATH"] = os.path.join(td, "test.db")
            app_module = self._load_app_module()
            client = app_module.app.test_client()

            current = client.get("/api/state").get_json()["state"]
            current["products"] = [{"id": 1, "name": "X", "cat": "C", "um": "pz", "prices": {"A": 1.0}}]
            current["suppliers"] = [{"name": "A", "min": 10, "current": 0}]
            ok = client.post("/api/state", json={"state": current}).get_json()
            self.assertTrue(ok.get("ok"))

            incoming = dict(current)
            incoming["products"] = []
            r = client.post("/api/state", json={"state": incoming})
            self.assertEqual(r.status_code, 409)

    def test_delete_order_endpoints_and_audit(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["APP_DB_PATH"] = os.path.join(td, "test.db")
            app_module = self._load_app_module()
            client = app_module.app.test_client()

            state = client.get("/api/state").get_json()["state"]
            state["inbox"] = [{"id": 111, "dept": "CUCINA", "staff": "Mario Rossi", "text": "test", "date": "01/01/2026 10:00"}]
            state["archive"] = [{"orderId": 222, "dept": "CUCINA", "staff": "Mario Rossi", "text": "test", "total": 1.0, "ts": 1, "date": "01/01/2026 10:00", "items": []}]
            ok = client.post("/api/state", json={"state": state, "force": True}).get_json()
            self.assertTrue(ok.get("ok"))

            r_forbidden = client.post("/api/admin/delete-order", json={"list": "inbox", "id": 111})
            self.assertEqual(r_forbidden.status_code, 403)

            r_ok = client.post("/api/admin/delete-order", json={"role": "admin", "actor": "admin", "list": "inbox", "id": 111})
            self.assertEqual(r_ok.status_code, 200)
            st2 = client.get("/api/state").get_json()["state"]
            self.assertEqual(len(st2.get("inbox") or []), 0)

            r_ok2 = client.post("/api/admin/delete-order", json={"role": "admin", "actor": "admin", "list": "archive", "id": 222})
            self.assertEqual(r_ok2.status_code, 200)
            st3 = client.get("/api/state").get_json()["state"]
            self.assertEqual(len(st3.get("archive") or []), 0)

            audit = client.get("/api/admin/orders-audit").get_json()
            self.assertTrue(audit.get("ok"))
            self.assertTrue(len(audit.get("audit") or []) >= 2)


if __name__ == "__main__":
    unittest.main()
