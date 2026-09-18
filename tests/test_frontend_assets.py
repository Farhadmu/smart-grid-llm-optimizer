"""Tests for frontend demonstration assets, static files, and contract compatibility."""

import json
import os
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"


class TestFrontendAssets(unittest.TestCase):
    """Verify frontend static assets exist and adhere to the contract."""

    def test_required_static_files_exist(self):
        index_html = FRONTEND_DIR / "index.html"
        styles_css = FRONTEND_DIR / "styles.css"
        app_js = FRONTEND_DIR / "app.js"
        samples_json = FRONTEND_DIR / "sample_cases.json"
        readme = FRONTEND_DIR / "README.md"

        self.assertTrue(index_html.exists(), "frontend/index.html missing")
        self.assertTrue(styles_css.exists(), "frontend/styles.css missing")
        self.assertTrue(app_js.exists(), "frontend/app.js missing")
        self.assertTrue(samples_json.exists(), "frontend/sample_cases.json missing")
        self.assertTrue(readme.exists(), "frontend/README.md missing")

    def test_public_samples_match_spec_contract(self):
        samples_path = FRONTEND_DIR / "sample_cases.json"
        with open(samples_path) as f:
            samples = json.load(f)

        self.assertEqual(len(samples), 10, "Should contain all 10 public samples")
        for sample in samples:
            self.assertIn("id", sample)
            self.assertIn("input", sample)
            inp = sample["input"]
            self.assertIn("scenario_id", inp)
            self.assertIn("operator_notes", inp)
            self.assertIn("hours", inp)
            self.assertIn("battery", inp)
            self.assertEqual(len(inp["hours"]), 24)
            self.assertGreaterEqual(len(inp["operator_notes"]), 1)
            self.assertLessEqual(len(inp["operator_notes"]), 3)

    def test_frontend_does_not_contain_secrets(self):
        # Scan frontend files to ensure no API keys or tokens are hardcoded
        sensitive_patterns = ["AIzaSy", "sk-proj-", "sk-live-", "Bearer "]
        for file_name in ["index.html", "styles.css", "app.js", "sample_cases.json"]:
            file_path = FRONTEND_DIR / file_name
            content = file_path.read_text(encoding="utf-8")
            for pattern in sensitive_patterns:
                self.assertNotIn(pattern, content, f"Sensitive pattern {pattern} found in {file_name}")

    def test_frontend_mentions_non_judging_boundary(self):
        index_html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
        readme = (FRONTEND_DIR / "README.md").read_text(encoding="utf-8")

        self.assertIn("Disclaimer", index_html)
        self.assertIn("POST /optimize-energy", index_html)
        self.assertIn("optional demonstration", readme)

    def test_judge_proof_and_explainability_elements_exist(self):
        index_html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn("judgeTrustPanel", index_html, "Judge trust panel missing")
        self.assertIn("tacticalRationaleCard", index_html, "Tactical decision rationale missing")
        self.assertIn("interpretationTraceCard", index_html, "Interpretation trace matrix missing")
        self.assertIn("whatIfSimulatorCard", index_html, "What-if sensitivity simulator missing")
        self.assertIn("Bangladesh National Grid Context", index_html, "Bangladesh grid context missing")
        self.assertIn("toggleBaselineBtn", index_html, "Baseline toggle button missing")


if __name__ == "__main__":
    unittest.main()
