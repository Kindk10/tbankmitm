"""Smoke tests for logo URL helpers (no mitmproxy import)."""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# Load bank_filter only
spec = importlib.util.spec_from_file_location("bank_filter", os.path.join(ROOT, "bank_filter.py"))
bank_filter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bank_filter)


class FakeRequest:
    def __init__(self, host, port, path):
        self.host = host
        self.port = port
        self.path = path


class FakeFlow:
    def __init__(self, host, port, path):
        self.request = FakeRequest(host, port, path)


def test_map_twice():
    f = FakeFlow("www.tbank-online.com", 443, "/__tbankmitm_panel/panel-bank-logo?u=test")
    assert bank_filter.map_same_origin_panel_request(f) is True
    assert f.request.path.startswith("/panel-bank-logo")
    assert bank_filter.bank_https_panel_request(f) is True


def test_inner_path_after_rewrite():
    f = FakeFlow("www.tbank-online.com", 443, "/panel-bank-logo?u=test")
    assert bank_filter.bank_https_panel_request(f) is True
    assert f.request.path == "/panel-bank-logo?u=test"


if __name__ == "__main__":
    test_map_twice()
    test_inner_path_after_rewrite()
    print("ok")
