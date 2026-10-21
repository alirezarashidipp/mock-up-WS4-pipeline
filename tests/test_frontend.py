"""Offline checks for page controls and static assets; no browser required."""

import re
import unittest
from pathlib import Path

from app.ui import dashboard_app, review_app


class FrontendTests(unittest.TestCase):
    def check_page(self, module, page, folder):
        path = Path(page().path)
        self.assertEqual(path.parent.name, folder)
        html = path.read_text(encoding="utf-8")
        assets = next(route.app for route in module.app.routes if route.path == "/assets")
        urls = re.findall(r'(?:src|href)="/assets/([^"]+)"', html)
        self.assertIn("style.css", urls)
        self.assertIn(f"{folder}/app.js", urls)
        for url in urls:
            _, file_info = assets.lookup_path(url)
            self.assertIsNotNone(file_info, f"Missing asset: {url}")

        script = (path.parent / "app.js").read_text(encoding="utf-8")
        html_ids = set(re.findall(r'id="([^"]+)"', html))
        script_ids = set(re.findall(r'\$\("([^"]+)"\)', script))
        self.assertFalse(script_ids - html_ids, f"Missing controls: {script_ids - html_ids}")
        return html

    def test_review_page(self):
        html = self.check_page(review_app, review_app.review_page, "review")
        for control in ("decision-form", "final-class", "user-reason", "finalize", "model-input"):
            self.assertIn(f'id="{control}"', html)
        self.assertIn('value="HSBC"', html)
        self.assertIn('value="SUPPLIER"', html)

    def test_dashboard_page(self):
        html = self.check_page(dashboard_app, dashboard_app.dashboard_page, "dashboard")
        for control in ("total-count", "HSBC-count", "SUPPLIER-count", "final-rows", "reload"):
            self.assertIn(f'id="{control}"', html)


if __name__ == "__main__":
    unittest.main()
