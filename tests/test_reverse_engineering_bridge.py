"""
Unit tests for the ReverseEngineeringBridge and ReverseEngineeringAnalyzer.
Tests tool discovery, Phase 0 fingerprinting, parsing, and FastAPI endpoints.
"""

import os
import sys
import unittest
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.reverse_engineering_bridge import ReverseEngineeringBridge
from core.re_analyzer import ReverseEngineeringAnalyzer


class TestReverseEngineeringBridge(unittest.TestCase):

    def test_check_tools(self):
        tools = ReverseEngineeringBridge.check_tools()
        self.assertIn("fingerprint_ready", tools)
        self.assertIn("jadx_ready", tools)
        self.assertIn("skill_plugin_installed", tools)
        self.assertTrue(tools["fingerprint_ready"], "fingerprint.sh should be discoverable")

    def test_get_fingerprint_script(self):
        script = ReverseEngineeringBridge.get_fingerprint_script()
        self.assertIsNotNone(script)
        self.assertTrue(script.is_file())
        self.assertTrue(os.access(script, os.X_OK))

    def test_parse_fingerprint_output(self):
        sample_output = """
Framework: Native Android (Kotlin + Jetpack Compose)
Rationale: androidx.compose detected in classes.dex
Obfuscation: LOW (2.4% short identifiers)
HTTP stack: Retrofit OkHttp
DI: Dagger Hilt
Serialization: Moshi
Third-party SDKs: Firebase  AppsFlyer
Recommended next step: Decompile with jadx -d out classes.dex
"""
        parsed = ReverseEngineeringBridge._parse_fingerprint_output(sample_output)
        self.assertTrue(parsed["success"])
        self.assertEqual(parsed["framework"], "Native Android (Kotlin + Jetpack Compose)")
        self.assertEqual(parsed["obfuscation"], "LOW (2.4% short identifiers)")
        self.assertIn("Retrofit", parsed["http_stack"])
        self.assertIn("OkHttp", parsed["http_stack"])
        self.assertIn("Dagger", parsed["di"])
        self.assertIn("Firebase", parsed["third_party_sdks"])

    def test_re_analyzer_tools_status(self):
        analyzer = ReverseEngineeringAnalyzer()
        status = analyzer.check_tools()
        self.assertIn("fingerprint_ready", status)
        self.assertIn("jadx_ready", status)
        self.assertTrue(status["fingerprint_ready"])

    def test_re_analyzer_derive_strategy(self):
        analyzer = ReverseEngineeringAnalyzer()

        # Compose strategy
        report_compose = {
            "framework": "Native Android (Kotlin + Jetpack Compose)",
            "obfuscation_level": "LOW",
            "http_stack": ["OkHttp"],
            "native_libs": ["arm64-v8a"]
        }
        strat_compose = analyzer._derive_strategy(report_compose)
        self.assertEqual(strat_compose["code"], "STRATEGY_NATIVE_COMPOSE")
        self.assertTrue(strat_compose["enforce_landscape"])

        # Flutter strategy
        report_flutter = {
            "framework": "Flutter",
            "obfuscation_level": "LOW",
            "http_stack": [],
            "native_libs": ["arm64-v8a", "armeabi-v7a"]
        }
        strat_flutter = analyzer._derive_strategy(report_flutter)
        self.assertEqual(strat_flutter["code"], "STRATEGY_FLUTTER")
        self.assertTrue(strat_flutter["preserve_dex"])

        # React Native strategy
        report_rn = {
            "framework": "React Native",
            "obfuscation_level": "MODERATE",
            "http_stack": [],
            "native_libs": []
        }
        strat_rn = analyzer._derive_strategy(report_rn)
        self.assertEqual(strat_rn["code"], "STRATEGY_REACT_NATIVE")

    def test_fingerprint_jiotv_if_present(self):
        jiotv_path = Path.home() / "Downloads" / "jiotv_7.0.9.apk"
        if not jiotv_path.is_file():
            self.skipTest("jiotv_7.0.9.apk not present in Downloads")

        result = ReverseEngineeringBridge.fingerprint(jiotv_path)
        self.assertTrue(result["success"])
        self.assertIn("Compose", result["framework"])
        self.assertIn("Retrofit", result["http_stack"])


class TestWebServerFingerprintEndpoint(unittest.TestCase):

    def setUp(self):
        from fastapi.testclient import TestClient
        from web.server import app
        self.client = TestClient(app)

    def test_api_fingerprint_missing_filename(self):
        res = self.client.get("/api/fingerprint")
        self.assertEqual(res.status_code, 400)

    def test_api_fingerprint_nonexistent(self):
        res = self.client.get("/api/fingerprint?filename=nonexistent_file.apk")
        self.assertEqual(res.status_code, 404)

    def test_api_fingerprint_sample_if_present(self):
        sample = PROJECT_ROOT / "samples" / "sample-smartphone.apk"
        if not sample.is_file():
            self.skipTest("sample-smartphone.apk not present")
        res = self.client.get(f"/api/fingerprint/{sample.name}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("framework", data)
        self.assertIn("obfuscation_level", data)


if __name__ == "__main__":
    unittest.main()
