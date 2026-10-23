"""通过实际 HTTP 读取原始字节，核对 JSON 压缩协商和媒体响应"""
import gzip
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
import os
import threading

import pytest

from lessonweave.server import Handler


@pytest.fixture
def compression_server(tmp_path):
    large = {"items": [{"id": index, "text": "这是正文与来源映射，读取后内容保持一致" * 6} for index in range(120)]}
    small = {"status": "ready"}
    large_bytes = json.dumps(large, ensure_ascii=False).encode("utf-8")
    (tmp_path / "source-pack.json").write_bytes(large_bytes)
    (tmp_path / "small.json").write_text(json.dumps(small), "utf-8")
    binary = os.urandom(4096)
    for name in ("material.pdf", "reading-package.zip", "original.wacz", "movie.mp4"):
        (tmp_path / name).write_bytes(binary)
    (tmp_path / "page.html").write_text("<p>原网页内容</p>" * 400, "utf-8")
    # 随机字节模拟已有文件，压缩后变大时继续发送原件
    (tmp_path / "uncompressible.json").write_bytes(binary)

    class TestHandler(Handler):
        def do_GET(self):
            if self.path == "/api/large":
                self.json(large)
            elif self.path == "/api/small":
                self.json(small)
            else:
                self.file(tmp_path / self.path.lstrip("/"))

    server = ThreadingHTTPServer(("127.0.0.1", 0), TestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def get(path, encoding=None, range_header=None):
        headers = {}
        if encoding is not None:
            headers["Accept-Encoding"] = encoding
        if range_header is not None:
            headers["Range"] = range_header
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        status, response_headers, body = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return status, response_headers, body

    yield get, large_bytes, binary
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.mark.parametrize("path", ["/api/large", "/source-pack.json"])
def test_json_gzip_raw_body_matches_identity_and_wire_length(compression_server, path):
    get, expected, _ = compression_server
    status, headers, raw = get(path, "gzip")
    identity_status, identity_headers, identity = get(path, "identity")
    assert status == identity_status == 200
    assert headers["Content-Encoding"] == "gzip"
    assert "Content-Encoding" not in identity_headers
    assert headers["Vary"] == identity_headers["Vary"] == "Accept-Encoding"
    assert int(headers["Content-Length"]) == len(raw) < len(identity)
    assert int(identity_headers["Content-Length"]) == len(identity)
    assert gzip.decompress(raw) == identity == expected
    assert headers["Cache-Control"] == identity_headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("encoding,compressed", [
    (None, False), ("identity", False), ("br", False),
    ("gzip;q=0", False), ("gzip;q=0, *;q=1", False),
    ("*;q=1, gzip;q=0", False), ("*;q=0", False),
    ("gzip;q=0.3", True), ("GZIP ; q=1", True), ("*;q=1", True),
])
def test_json_respects_accept_encoding_including_explicit_gzip_zero(compression_server, encoding, compressed):
    get, expected, _ = compression_server
    status, headers, raw = get("/api/large", encoding)
    assert status == 200
    assert (headers.get("Content-Encoding") == "gzip") is compressed
    assert int(headers["Content-Length"]) == len(raw)
    assert (gzip.decompress(raw) if compressed else raw) == expected


@pytest.mark.parametrize("path", ["/api/small", "/small.json", "/uncompressible.json"])
def test_small_or_larger_after_compression_json_keeps_original_bytes(compression_server, path):
    get, _, _ = compression_server
    status, headers, raw = get(path, "gzip")
    _, _, identity = get(path, "identity")
    assert status == 200 and "Content-Encoding" not in headers
    assert raw == identity
    assert int(headers["Content-Length"]) == len(raw)


@pytest.mark.parametrize("path", ["/api/large", "/source-pack.json"])
def test_json_range_request_keeps_full_existing_identity_response(compression_server, path):
    get, expected, _ = compression_server
    status, headers, raw = get(path, "gzip", "bytes=0-19")
    assert status == 200
    assert "Content-Encoding" not in headers and "Content-Range" not in headers
    assert raw == expected and int(headers["Content-Length"]) == len(expected)


@pytest.mark.parametrize("path", ["/material.pdf", "/reading-package.zip", "/original.wacz", "/movie.mp4", "/page.html"])
def test_non_json_is_unchanged_even_with_gzip_negotiation(compression_server, path):
    get, _, _ = compression_server
    status, headers, raw = get(path, "gzip")
    _, _, identity = get(path, "identity")
    assert status == 200 and "Content-Encoding" not in headers
    assert "Vary" not in headers
    assert raw == identity and int(headers["Content-Length"]) == len(raw)


@pytest.mark.parametrize("path", ["/original.wacz", "/movie.mp4"])
def test_media_partial_response_retains_existing_206_and_bytes(compression_server, path):
    get, _, binary = compression_server
    status, headers, raw = get(path, "gzip", "bytes=11-30")
    assert status == 206 and "Content-Encoding" not in headers
    assert headers["Content-Range"] == "bytes 11-30/4096"
    assert headers["Accept-Ranges"] == "bytes" and headers["Content-Length"] == "20"
    assert raw == binary[11:31]
