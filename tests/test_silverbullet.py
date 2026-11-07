"""Tests against a fake SilverBullet /.fs server running on localhost."""

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

import pytest

from paper_window.pages import StaleTaskError
from paper_window.silverbullet import SilverBulletClient, SilverBulletError
from paper_window.sync import PageIndex

USER, PASSWORD = "admin", "secret"
TAGGED = "---\ntags: [paper-window]\n---\n- [ ] first\n- [x] second\n"


class FakeSilverBullet:
    def __init__(self):
        self.files = {
            "Work/Inbox.md": {"text": TAGGED, "modified": 1},
            "Plain.md": {"text": "- [ ] not tagged\n", "modified": 1},
            "_plug/internal.md": {"text": TAGGED, "modified": 1},
        }
        self.writes = []
        self.requests = []
        self.auth_headers = []

    def handler(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def _authorized(self):
                expected = "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
                fake.auth_headers.append(self.headers.get("Authorization"))
                if self.headers.get("Authorization") != expected:
                    self.send_response(401)
                    self.end_headers()
                    return False
                return True

            def _send(self, status, body=b"", content_type="application/json"):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if not self._authorized():
                    return
                if self.path == "/.fs":
                    listing = [
                        {"name": name, "lastModified": meta["modified"], "contentType": "text/markdown"}
                        for name, meta in fake.files.items()
                    ]
                    return self._send(200, json.dumps(listing).encode())
                name = unquote(self.path[len("/.fs/"):])
                if name not in fake.files:
                    return self._send(404, b"not found", "text/plain")
                fake.requests.append(("GET", name))
                self._send(200, fake.files[name]["text"].encode(), "text/markdown")

            def do_PUT(self):
                if not self._authorized():
                    return
                name = unquote(self.path[len("/.fs/"):])
                length = int(self.headers.get("Content-Length", 0))
                text = self.rfile.read(length).decode()
                fake.writes.append((name, text))
                fake.files[name] = {"text": text, "modified": fake.files[name]["modified"] + 1}
                self._send(200, b"")

        return Handler


@pytest.fixture
def server():
    fake = FakeSilverBullet()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), fake.handler())
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    fake.url = f"http://127.0.0.1:{httpd.server_port}"
    yield fake
    httpd.shutdown()
    httpd.server_close()


def client_for(fake, password=PASSWORD):
    return SilverBulletClient(fake.url, username=USER, password=password, timeout=5)


def test_list_skips_internal_and_non_markdown_files(server):
    names = [f.name for f in client_for(server).list_markdown_files()]
    assert sorted(names) == ["Plain.md", "Work/Inbox.md"]


def test_wrong_password_raises(server):
    with pytest.raises(SilverBulletError, match="401"):
        client_for(server, password="wrong").list_markdown_files()


def test_unreachable_server_raises():
    client = SilverBulletClient("http://127.0.0.1:1", timeout=1)
    with pytest.raises(SilverBulletError):
        client.list_markdown_files()


def test_index_returns_only_tagged_pages_and_caches_by_modified_time(server):
    index = PageIndex(client_for(server), "paper-window")
    pages = index.refresh()
    assert [p.name for p in pages] == ["Work/Inbox"]
    assert [t.text for t in pages[0].tasks] == ["first", "second"]

    server.requests.clear()
    index.refresh()
    assert server.requests == []  # unchanged lastModified: nothing re-downloaded


def test_toggle_writes_back_and_updates_page(server):
    index = PageIndex(client_for(server), "paper-window")
    page = index.refresh()[0]
    updated = index.toggle(page, 0)
    assert server.writes[-1][0] == "Work/Inbox.md"
    assert "- [x] first" in server.writes[-1][1].split("\n")
    assert updated.tasks[0].done is True


def test_toggle_detects_task_changed_on_server(server):
    index = PageIndex(client_for(server), "paper-window")
    page = index.refresh()[0]
    server.files["Work/Inbox.md"]["text"] = TAGGED.replace("first", "renamed")
    with pytest.raises(StaleTaskError):
        index.toggle(page, 0)
    assert server.writes == []
