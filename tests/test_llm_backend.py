"""
Tests unitaires pour le backend LLM `agy`, ContentEngine et la résolution de configuration.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.content.engine import CTA_SUFFIX, ContentEngine
from modules.core.config_loader import _resolve_env_vars
from modules.llm.agy_backend import AgyBackend
from modules.llm.base import LLMAuthError, LLMError


class TestConfigLoader(unittest.TestCase):
    @patch.dict("os.environ", {"EXISTING_VAR": "hello"}, clear=False)
    def test_resolve_env_vars_with_default(self):
        data = {
            "a": "${EXISTING_VAR}",
            "b": "${MISSING_VAR:-fallback_val}",
            "c": "${MISSING_EMPTY:-}",
        }
        resolved = _resolve_env_vars(data)
        self.assertEqual(resolved["a"], "hello")
        self.assertEqual(resolved["b"], "fallback_val")
        self.assertEqual(resolved["c"], "")


class TestAgyBackend(unittest.TestCase):
    def setUp(self):
        self.backend = AgyBackend(
            {
                "binary": "agy",
                "model": "gemini-3.8-flash-medium",
                "home": "",
                "workdir": "data/agy-workspace",
                "timeout_seconds": 30,
                "max_retries": 2,
            }
        )

    @patch("modules.llm.agy_backend.subprocess.run")
    def test_generate_json_success(self, mock_run):
        payload = {
            "status": "SUCCESS",
            "duration_seconds": 12.3,
            "structured_output": {"title": "عنوان تجريبي", "keywords": ["عنوان"]},
            "usage": {"total_tokens": 1234},
        }
        mock_run.return_value = subprocess.CompletedProcess(
            args=["agy"], returncode=0, stdout=json.dumps(payload), stderr=""
        )

        res = self.backend.generate_json("prompt", {"type": "object"})
        self.assertEqual(res["title"], "عنوان تجريبي")
        self.assertEqual(mock_run.call_count, 1)

    @patch("modules.llm.agy_backend.subprocess.run")
    def test_generate_json_auth_error_no_retry(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["agy"],
            returncode=1,
            stdout="",
            stderr="Error: Not logged in. Please sign in first.",
        )

        with self.assertRaises(LLMAuthError):
            self.backend.generate_json("prompt", {"type": "object"})
        # Ne doit pas faire de retry sur une erreur d'authentification
        self.assertEqual(mock_run.call_count, 1)

    @patch("modules.llm.agy_backend.time.sleep", return_value=None)
    @patch("modules.llm.agy_backend.subprocess.run")
    def test_generate_json_retry_then_success(self, mock_run, _mock_sleep):
        fail_proc = subprocess.CompletedProcess(
            args=["agy"], returncode=1, stdout="invalid json", stderr="server busy"
        )
        ok_proc = subprocess.CompletedProcess(
            args=["agy"],
            returncode=0,
            stdout=json.dumps(
                {
                    "status": "SUCCESS",
                    "structured_output": {"ok": True},
                    "duration_seconds": 5.0,
                }
            ),
            stderr="",
        )
        mock_run.side_effect = [fail_proc, ok_proc]

        res = self.backend.generate_json("prompt", {"type": "object"})
        self.assertEqual(res, {"ok": True})
        self.assertEqual(mock_run.call_count, 2)

    @patch("modules.llm.agy_backend.time.sleep", return_value=None)
    @patch("modules.llm.agy_backend.subprocess.run")
    def test_generate_json_timeout_raises_llm_error(self, mock_run, _mock_sleep):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["agy"], timeout=60)
        with self.assertRaises(LLMError):
            self.backend.generate_json("prompt", {"type": "object"})
        self.assertEqual(mock_run.call_count, 2)


class TestContentEngine(unittest.TestCase):
    def test_generate_package_normalizes_fields(self):
        fake_backend = MagicMock()
        fake_backend.name = "agy"
        fake_backend.generate_json.return_value = {
            "title": "  ارتفاع أسعار الذهب عالمياً  ",
            "keywords": ["ارتفاع", "الذهب", "عالمياً", "زائد"],
            "image_query": "",
            "caption": "ما رأيكم في هذا الارتفاع؟ #ذهب",
            "detail_comment": "***\nشهدت الأسواق العالمية اليوم قفزة جديدة.\n---\nتفاصيل إضافية.",
        }

        engine = ContentEngine(backend=fake_backend)
        pkg = engine.generate_package("النص الأصلي للخبر")

        self.assertIsNotNone(pkg)
        self.assertEqual(pkg["title"], "ارتفاع أسعار الذهب عالمياً")
        self.assertEqual(len(pkg["keywords"]), 3)
        self.assertEqual(pkg["image_query"], "breaking news")
        self.assertTrue(pkg["caption"].endswith(CTA_SUFFIX))
        self.assertNotIn("***", pkg["detail_comment"])
        self.assertNotIn("---", pkg["detail_comment"])


if __name__ == "__main__":
    unittest.main()
