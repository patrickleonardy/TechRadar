"""Test the HTTP client without importing the application's optional services."""

import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import requests

spec = importlib.util.spec_from_file_location(
    "trendradar_http_client", Path(__file__).parents[1] / "trendradar/ai/client.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
AIClient = module.AIClient


class AIClientTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"AI_API_KEY": ""})
        env.start()
        self.addCleanup(env.stop)
        self.config = {
            "MODEL": "openai/organization/model",
            "API_BASE": "https://example.invalid/v1/",
            "API_KEY": "test-secret",
            "NUM_RETRIES": 0,
        }
        self.session = MagicMock()
        self.response = self.session.post.return_value.__enter__.return_value
        self.response.status_code = 200
        self.response.json.return_value = {"choices": [{"message": {"content": "reply"}}]}
        session = patch.object(module.requests, "Session")
        session.start().return_value.__enter__.return_value = self.session
        self.addCleanup(session.stop)
        sleep = patch.object(module.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)

    def test_direct_request_and_credentials(self):
        self.assertEqual(AIClient(self.config).chat([]), "reply")
        args, options = self.session.post.call_args
        self.assertEqual(args, ("https://example.invalid/v1/chat/completions",))
        self.assertEqual(options["json"]["model"], "organization/model")
        self.assertEqual(options["headers"]["Authorization"], "Bearer test-secret")
        self.assertFalse(options["allow_redirects"])
        self.assertFalse(self.session.trust_env)
        self.assertNotIn("api_key", options["json"])

    def test_keyless_local_server_and_raw_model_id(self):
        client = AIClient({**self.config, "API_BASE": "http://ollama:11434/v1", "MODEL": "org/model", "API_KEY": ""})
        self.assertEqual(client.validate_config(), (True, ""))
        client.chat([])
        options = self.session.post.call_args.kwargs
        self.assertNotIn("Authorization", options["headers"])
        self.assertEqual(options["json"]["model"], "org/model")

    def test_invalid_endpoint_fails_before_request(self):
        for base in ("", "file:///tmp/model", "https://user:pass@host/v1", "https://host/v1?key=x", "https://host:bad/v1", "http://remote/v1"):
            with self.subTest(base=base):
                with self.assertRaises(ValueError):
                    AIClient({**self.config, "API_BASE": base}).chat([])
        self.session.post.assert_not_called()

    def test_extra_fields_and_call_overrides(self):
        client = AIClient({**self.config, "EXTRA_PARAMS": {
            "top_p": 0.8, "model": "wrong", "messages": ["wrong"],
            "api_base": "https://wrong.invalid/v1", "api_key": "wrong",
            "stream": True, "extra_headers": {"X-Trace": "test"},
        }})
        client.chat([], top_p=0.2, temperature=0.4, max_tokens=0, timeout=5)
        options = self.session.post.call_args.kwargs
        self.assertEqual(options["json"], {
            "model": "organization/model", "messages": [], "temperature": 0.4,
            "stream": False, "top_p": 0.2,
        })
        self.assertEqual(options["timeout"], 5)
        self.assertEqual(options["headers"]["X-Trace"], "test")

    def test_extra_headers_cannot_redirect_or_replace_auth(self):
        for header in ("Authorization", "HOST", "Proxy-Authorization", "Content-Length"):
            with self.subTest(header=header), self.assertRaises(ValueError):
                AIClient({**self.config, "EXTRA_PARAMS": {"extra_headers": {header: "wrong"}}}).chat([])
        self.session.post.assert_not_called()

    def test_redirect_is_rejected_without_following(self):
        self.response.status_code = 302
        with self.assertRaisesRegex(RuntimeError, "HTTP 302"):
            AIClient(self.config).chat([])
        self.session.post.assert_called_once()

    def test_transient_errors_retry_but_auth_failure_does_not(self):
        self.response.status_code = 429
        with self.assertRaisesRegex(RuntimeError, "HTTP 429"):
            AIClient({**self.config, "NUM_RETRIES": 2}).chat([])
        self.assertEqual(self.session.post.call_count, 3)
        self.session.post.reset_mock()
        self.response.status_code = 401
        with self.assertRaisesRegex(RuntimeError, "HTTP 401"):
            AIClient({**self.config, "NUM_RETRIES": 2}).chat([])
        self.session.post.assert_called_once()

    def test_fallback_stays_on_same_endpoint(self):
        self.response.status_code = 503
        with self.assertRaises(RuntimeError):
            AIClient({**self.config, "FALLBACK_MODELS": ["backup"]}).chat([])
        calls = self.session.post.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(c.args[0] == "https://example.invalid/v1/chat/completions" for c in calls))
        self.assertEqual(calls[-1].kwargs["json"]["model"], "backup")

    def test_errors_do_not_include_remote_body_or_exception_secrets(self):
        self.session.post.side_effect = requests.ConnectionError("test-secret in URL")
        with self.assertRaisesRegex(RuntimeError, "^AI endpoint connection failed.$"):
            AIClient(self.config).chat([])
        self.session.post.side_effect = None
        self.response.status_code = 500
        self.response.text = "test-secret in server error"
        with self.assertRaisesRegex(RuntimeError, "^AI endpoint returned HTTP 500.$"):
            AIClient(self.config).chat([])

    def test_invalid_response_and_content_blocks(self):
        self.response.json.return_value = {}
        with self.assertRaisesRegex(RuntimeError, "invalid chat response"):
            AIClient(self.config).chat([])
        self.response.json.return_value = {"choices": [{"message": {"content": [{"text": "one"}, {"text": "two"}]}}]}
        self.assertEqual(AIClient(self.config).chat([]), "one\ntwo")


if __name__ == "__main__":
    unittest.main()
