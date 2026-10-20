"""scripts/check_links.py のテスト（ネットワークには出ない. 応答は差し替える）."""

import socket
import ssl
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_links as cl  # noqa: E402
from _util import rmtree  # noqa: E402


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x.invalid/", code, "x", {}, None)


class FakeRequest:
    """(URL, メソッド) ごとの応答を順に返す. 例外なら投げる."""

    def __init__(self, answers: dict):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, url, method, timeout):
        self.calls.append((url, method))
        queue = self.answers[(url, method)]
        answer = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(answer, BaseException):
            raise answer
        return answer


def probe(answers: dict, url="https://a.org/"):
    fake = FakeRequest(answers)
    return cl.probe(url, sleep=lambda _s: None, request=fake), fake


class CollectTest(unittest.TestCase):
    def setUp(self):
        self.site = Path(tempfile.mkdtemp())
        (self.site / "ch").mkdir()
        (self.site / "index.html").write_text(
            '<a href="https://a.org/doc#part">a</a> <a href="../ch/">内部</a> <a href="mailto:x@a.org">m</a>'
            '<a href="http://localhost:8080">l</a> <a href="https://dev.example.com/x">e</a>'
            '<a href="https://example.org">e2</a> <a href="https://&lt;host&gt;/">書きかけ</a>',
            encoding="utf-8",
        )
        (self.site / "ch" / "index.html").write_text(
            '<p><a class="x" href="https://a.org/doc">a</a></p>', encoding="utf-8"
        )

    def tearDown(self):
        rmtree(self.site)

    def test_collects_external_links_once_without_examples(self):
        self.assertEqual(cl.collect(self.site), {"https://a.org/doc": {"index.html", "ch/index.html"}})

    def test_is_example(self):
        for url in [
            "http://127.0.0.1:9090",
            "http://[::1]:8080/",
            "http://0.0.0.0:8080",
            "http://192.168.0.10/",
            "https://api.example.net/",
            "https://foo.test/",
            "https://{{ x }}/",
        ]:
            self.assertTrue(cl.is_example(url), url)
        self.assertFalse(cl.is_example("https://docs.spring.io/spring-boot/"))
        self.assertFalse(cl.is_example("https://notexample.com/"))


class ProbeTest(unittest.TestCase):
    def test_ok(self):
        (state, _), fake = probe({("https://a.org/", "HEAD"): [200]})
        self.assertEqual(state, "ok")
        self.assertEqual(fake.calls, [("https://a.org/", "HEAD")])

    def test_head_rejected_falls_back_to_get(self):
        (state, _), _ = probe({("https://a.org/", "HEAD"): [http_error(405)], ("https://a.org/", "GET"): [200]})
        self.assertEqual(state, "ok")

    def test_404_is_broken(self):
        both = {("https://a.org/", "HEAD"): [http_error(404)], ("https://a.org/", "GET"): [http_error(404)]}
        (state, detail), _ = probe(both)
        self.assertEqual((state, detail), ("broken", "HTTP 404"))

    def test_403_and_429_are_unsure_not_broken(self):
        for code in (403, 429):
            both = {("https://a.org/", "HEAD"): [http_error(code)], ("https://a.org/", "GET"): [http_error(code)]}
            (state, _), fake = probe(both)
            self.assertEqual(state, "unsure")
            self.assertEqual(len(fake.calls), 2 * (cl.RETRIES + 1))  # 再試行する

    def test_5xx_retries_then_succeeds(self):
        get = [http_error(503), 200]
        (state, _), _ = probe({("https://a.org/", "HEAD"): [http_error(503)], ("https://a.org/", "GET"): get})
        self.assertEqual(state, "ok")

    def test_dns_failure_and_bad_certificate_are_broken(self):
        dns = urllib.error.URLError(socket.gaierror(-2, "Name or service not known"))
        (state, _), _ = probe({("https://a.org/", "HEAD"): [dns]})
        self.assertEqual(state, "broken")
        cert = urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))
        (state, _), _ = probe({("https://a.org/", "HEAD"): [cert]})
        self.assertEqual(state, "broken")

    def test_timeout_is_unsure(self):
        (state, _), _ = probe({("https://a.org/", "HEAD"): [TimeoutError("timed out")]})
        self.assertEqual(state, "unsure")


class ReportTest(unittest.TestCase):
    def test_report_lists_broken_and_unsure(self):
        results = [
            cl.Result("https://a.org/", "ok", "200", {"a.html"}),
            cl.Result("https://b.org/", "broken", "HTTP 404", {"x/index.html"}),
            cl.Result("https://c.org/", "unsure", "HTTP 403", {"y/index.html"}),
        ]
        text = cl.report(results)
        self.assertIn("外部リンク 3 件を確認: 切れている 1 件・確認できない 1 件", text)
        self.assertIn("- <https://b.org/> — HTTP 404（x/index.html）", text)
        self.assertLess(text.index("切れているリンク"), text.index("確認できないリンク"))

    def test_main_exit_codes(self):
        site = Path(tempfile.mkdtemp())
        try:
            self.assertEqual(cl.main([str(site / "none")]), 2)
            (site / "index.html").write_text("<p>リンクなし</p>", encoding="utf-8")
            self.assertEqual(cl.main([str(site)]), 0)
        finally:
            rmtree(site)


if __name__ == "__main__":
    unittest.main()
