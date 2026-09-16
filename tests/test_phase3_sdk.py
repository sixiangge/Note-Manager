"""Exercise actual optional SDKs against a local HTTP fixture, never real accounts."""

from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.util import find_spec
import json
import io
import os
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from src.llm import generate, test_connection as probe_connection
from src.teaching_config import TeachingConfig


@unittest.skipUnless(find_spec("openai") and find_spec("ollama"), "Optional model SDKs not installed")
class TestSdkIntegration(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.status = 200
        self.output = json.dumps({"answer": "测试回答", "discrepancies": []})
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self, payload):
                body = json.dumps(payload).encode("utf-8")
                self.send_response(owner.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                owner.requests.append(("GET", self.path, None, self.headers.get("User-Agent")))
                if self.path == "/api/tags":
                    self.respond({"models": [{"model": "fake:latest", "name": "fake:latest"}]})
                else:
                    self.respond({"object": "list", "data": [{"id": "fake", "object": "model"}]})

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.requests.append(("POST", self.path, payload, self.headers.get("User-Agent")))
                if owner.status != 200:
                    self.respond({"error": {"message": "SENSITIVE_TEST_SECRET", "type": "invalid_api_key"}})
                elif self.path == "/api/chat":
                    self.respond({"model": "fake", "message": {"role": "assistant", "content": owner.output}, "done": True})
                else:
                    self.respond({"id": "chatcmpl-fixture", "object": "chat.completion", "created": 0,
                                  "model": "fake", "choices": [{"index": 0, "finish_reason": "stop",
                                      "message": {"role": "assistant", "content": owner.output}}]})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.env = patch.dict("os.environ", {"OPENAI_API_KEY": "dummy-test-key"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_both_adapters_generate_and_probe(self):
        for provider, suffix in (("local", ""), ("api", "/v1")):
            config = TeachingConfig(provider=provider, model="fake", base_url=self.url + suffix)
            self.assertIn("连接成功", probe_connection(config))
            messages = [{"role": "system", "content": "return JSON"}, {"role": "user", "content": "fixture"}]
            result = generate(config, messages)
            self.assertEqual(result["answer"], "测试回答")
            self.assertEqual(self.requests[-1][2]["messages"], messages)
        self.assertEqual([r[0] for r in self.requests], ["GET", "POST", "GET", "POST"])
        self.assertEqual([r[1] for r in self.requests], ["/api/tags", "/api/chat", "/v1/models", "/v1/chat/completions"])
        self.assertEqual([r[3] for r in self.requests[2:]], ["NoteManager/1.0", "NoteManager/1.0"])

    def test_remote_api_uses_system_proxy_only_when_enabled(self):
        config = TeachingConfig(
            provider="api",
            model="fake",
            base_url=self.url + "/v1",
        )
        unavailable_proxy = "http://127.0.0.1:1"
        with patch.dict(
            os.environ,
            {
                "HTTP_PROXY": unavailable_proxy,
                "HTTPS_PROXY": unavailable_proxy,
                "ALL_PROXY": unavailable_proxy,
                "NO_PROXY": "",
            },
        ):
            self.assertIn("连接成功", probe_connection(config))
            with self.assertRaises(RuntimeError):
                probe_connection(replace(config, use_system_proxy=True))

    def test_errors_are_redacted_not_retried(self):
        self.status = 401
        config = TeachingConfig(provider="api", model="fake", base_url=self.url + "/v1")
        with self.assertRaises(RuntimeError) as raised:
            generate(config, [{"role": "user", "content": "fixture"}])
        self.assertNotIn("SENSITIVE_TEST_SECRET", str(raised.exception))
        self.assertNotIn("dummy-test-key", str(raised.exception))
        self.assertEqual(len(self.requests), 1)

    def test_html_api_response_explains_the_expected_v1_endpoint(self):
        config = TeachingConfig(provider="api", model="fake", base_url=self.url)
        with patch(
            "openai.resources.chat.completions.Completions.create",
            return_value="<!doctype html><title>service page</title>",
        ):
            with self.assertRaisesRegex(RuntimeError, "OpenAI 兼容") as raised:
                generate(config, [{"role": "user", "content": "fixture"}])
        self.assertIn("/v1", str(raised.exception))

    def test_invalid_json_is_actionable_failure(self):
        self.output = "not JSON"
        with self.assertRaisesRegex(RuntimeError, "JSON"):
            generate(TeachingConfig(provider="local", model="fake", base_url=self.url),
                     [{"role": "user", "content": "fixture"}])

    def test_sdk_timeout_is_redacted(self):
        import httpx
        config = TeachingConfig(provider="api", model="fake", base_url=self.url + "/v1")
        with patch("openai.resources.chat.completions.Completions.create", side_effect=httpx.ReadTimeout("private")):
            with self.assertRaises(RuntimeError) as raised:
                generate(config, [])
        self.assertNotIn("private", str(raised.exception))

    def test_full_cli_pipeline_against_local_api(self):
        import main
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            note = root / "极限.md"
            note.write_text("---\ntitle: 极限\nsubject: 微积分\nchapter: 第一章\n"
                            "note_type: exam\n---\n极限定义 epsilon delta", encoding="utf-8")
            original = note.read_bytes()
            attachment = root / "课件.txt"
            attachment.write_text("极限定义 epsilon delta 的课件说明", encoding="utf-8")
            stream = io.StringIO()
            with patch.object(main, "NOTES_ROOT", root), redirect_stdout(stream):
                code = main.main(["teach", "极限定义", "--model", "api", "--model-name", "fake",
                                  "--base-url", self.url + "/v1", "--files", str(attachment)])
            self.assertEqual(code, 0, stream.getvalue())
            self.assertIn("测试回答", stream.getvalue())
            self.assertIn("[N1]", stream.getvalue())
            self.assertIn("[E1]", stream.getvalue())
            self.assertEqual(note.read_bytes(), original)
            self.assertEqual(len(self.requests), 1)
            self.assertNotIn(str(root), self.requests[0][2]["messages"][-1]["content"])
