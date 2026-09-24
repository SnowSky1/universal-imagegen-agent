import base64
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from universal_imagegen.client import ImageGenClient
from universal_imagegen.config import Settings
from universal_imagegen.models import EditRequest, GenerateRequest


class FakeImagesHandler(BaseHTTPRequestHandler):
    records: list[dict] = []

    def log_message(self, format, *args):  # noqa: A002
        return

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.records.append(
            {
                "method": "POST",
                "path": self.path,
                "headers": dict(self.headers),
                "body": body,
            }
        )

        if self.path == "/v1/images/generations":
            payload = base64.b64encode(b"generated-via-http").decode("ascii")
            self._send_json({"data": [{"b64_json": payload}]})
            return

        if self.path == "/v1/images/edits":
            host, port = self.server.server_address
            self._send_json({"data": [{"url": f"http://{host}:{port}/asset.png"}]})
            return

        self.send_error(404)

    def do_GET(self):  # noqa: N802
        self.records.append(
            {
                "method": "GET",
                "path": self.path,
                "headers": dict(self.headers),
                "body": b"",
            }
        )
        if self.path != "/asset.png":
            self.send_error(404)
            return
        payload = b"edited-via-url"
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, payload: dict) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


@contextmanager
def fake_images_api():
    FakeImagesHandler.records = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeImagesHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/v1", FakeImagesHandler.records
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_custom_base_url_headers_and_generation_endpoint(tmp_path: Path) -> None:
    with fake_images_api() as (base_url, records):
        settings = Settings(
            base_url=base_url,
            api_key="local-test-key",
            model="custom-image-model",
            default_headers={"X-Agent-Test": "enabled"},
            max_retries=0,
            output_dir=tmp_path,
        )
        out = tmp_path / "generated.png"
        result = ImageGenClient(settings).generate(
            GenerateRequest(prompt="A local integration test", out=out)
        )

    assert result.status == "ok"
    assert out.read_bytes() == b"generated-via-http"
    request = records[0]
    headers = {key.lower(): value for key, value in request["headers"].items()}
    assert request["path"] == "/v1/images/generations"
    assert headers["authorization"] == "Bearer local-test-key"
    assert headers["x-agent-test"] == "enabled"
    payload = json.loads(request["body"])
    assert payload["model"] == "custom-image-model"
    assert payload["prompt"] == "Primary request: A local integration test"


def test_edit_multipart_and_url_response_download(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"source-image")

    with fake_images_api() as (base_url, records):
        settings = Settings(
            base_url=base_url,
            api_key="local-test-key",
            model="custom-image-model",
            max_retries=0,
            output_dir=tmp_path,
        )
        out = tmp_path / "edited.png"
        result = ImageGenClient(settings).edit(
            EditRequest(
                prompt="Change only the background",
                images=(source,),
                out=out,
            )
        )

    assert result.status == "ok"
    assert out.read_bytes() == b"edited-via-url"
    post = next(record for record in records if record["method"] == "POST")
    get = next(record for record in records if record["method"] == "GET")
    assert post["path"] == "/v1/images/edits"
    assert post["headers"]["Content-Type"].startswith("multipart/form-data;")
    assert b"source-image" in post["body"]
    assert b"Change only the background" in post["body"]
    assert get["path"] == "/asset.png"
