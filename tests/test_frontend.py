"""Offline checks for dashboard controls and assets; no browser required."""

import re
import unittest
from pathlib import Path

from app.ui import dashboard_app


class FrontendTests(unittest.TestCase):
    def test_dashboard_page_and_assets(self):
        path = Path(dashboard_app.dashboard_page().path)
        self.assertEqual(path.parent.name, "dashboard")
        html = path.read_text(encoding="utf-8")
        assets = next(route.app for route in dashboard_app.app.routes if route.path == "/assets")
        urls = re.findall(r'(?:src|href)="/assets/([^"]+)"', html)
        self.assertIn("style.css", urls)
        self.assertIn("dashboard/app.js", urls)
        for url in urls:
            _, file_info = assets.lookup_path(url)
            self.assertIsNotNone(file_info, f"Missing asset: {url}")
        for control in ("total-count", "HSBC-count", "SUPPLIER-count", "final-rows", "reload"):
            self.assertIn(f'id="{control}"', html)

    def test_dashboard_controls_match_script(self):
        path = Path(dashboard_app.dashboard_page().path)
        html = path.read_text(encoding="utf-8")
        script = (path.parent / "app.js").read_text(encoding="utf-8")
        html_ids = set(re.findall(r'id="([^"]+)"', html))
        script_ids = set(re.findall(r'\$\("([^"]+)"\)', script))
        self.assertFalse(script_ids - html_ids, f"Missing controls: {script_ids - html_ids}")
        self.assertIn("/api/dashboard", script)
        self.assertIn("row.supplier_more_info", script)
        self.assertIn("text.textContent = columnName", script)
        self.assertNotIn("item.quote", script)
        self.assertNotIn("/api/review", script)
        self.assertNotIn('id="decision-form"', html)
        self.assertNotIn("8765", html)


if __name__ == "__main__":
    unittest.main()
