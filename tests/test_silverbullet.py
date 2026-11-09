"""Tests against a fake SilverBullet /.fs server running on localhost."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote

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
        self.login_count = 0
        self.valid_session = "session-0"
        self.require_auth = True
        self.token = None
        self.reject_fs = None
        self.login_response = None

    def handler(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def _authorized(self):
                fake.auth_headers.append(self.headers.get("Authorization"))
                if fake.reject_fs is not None:
                    self._send(fake.reject_fs, b"")
                    return False
                if fake.require_auth and (
                    self.headers.get("Cookie") != f"session={fake.valid_session}"
                    and (not fake.token or self.headers.get("Authorization") != f"Bearer {fake.token}")
                ):
                    self._send(401, b"")
                    return False
                return True

            def _send(self, status, body=b"", content_type="application/json"):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                if status == 302:
                    self.send_header("Location", "/.auth")
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                assert self.path == "/.auth"
                assert self.headers["Content-Type"] == "application/x-www-form-urlencoded"
                assert self.headers["X-Sync-Mode"] == "true"
                fake.login_count += 1
                length = int(self.headers.get("Content-Length", 0))
                form = parse_qs(self.rfile.read(length).decode(), keep_blank_values=True)
                if fake.login_response is not None:
                    return self._send(200, fake.login_response)
                if form.get("username") != [USER] or form.get("password") != [PASSWORD]:
                    return self._send(200, b'{"status":"error"}')
                fake.valid_session = f"session-{fake.login_count}"
                body = b'{"status":"ok"}'
                self.send_response(200)
                self.send_header("Set-Cookie", f"session={fake.valid_session}; Path=/; HttpOnly")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                assert self.headers["X-Sync-Mode"] == "true"
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
                assert self.headers["X-Sync-Mode"] == "true"
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
    with pytest.raises(SilverBulletError, match="login failed"):
        client_for(server, password="wrong").list_markdown_files()
    assert server.login_count == 1


def test_cookie_session_is_reused_and_refreshed(server):
    client = client_for(server)
    client.list_markdown_files()
    client.read_page("Work/Inbox.md")
    assert server.login_count == 1
    server.valid_session = "expired"
    client.write_page("Work/Inbox.md", TAGGED)
    assert server.login_count == 2
    assert server.writes == [("Work/Inbox.md", TAGGED)]
    assert all(header is None for header in server.auth_headers)


@pytest.mark.parametrize("status", [302, 401, 403])
def test_rejected_request_is_retried_only_once(server, status):
    server.reject_fs = status
    with pytest.raises(SilverBulletError, match=f"HTTP {status}"):
        client_for(server).list_markdown_files()
    assert server.login_count == 2


@pytest.mark.parametrize("response", [b"not json", b"[]", b'{"status":"error"}'])
def test_invalid_login_response_fails(server, response):
    server.login_response = response
    with pytest.raises(SilverBulletError, match="login"):
        client_for(server).list_markdown_files()
    assert server.login_count == 1


def test_bearer_token_takes_precedence(server):
    server.token = "test-token"
    client = SilverBulletClient(server.url, username=USER, password=PASSWORD, token=server.token)
    client.list_markdown_files()
    assert server.login_count == 0
    assert server.auth_headers == ["Bearer test-token"]


def test_unauthenticated_server(server):
    server.require_auth = False
    SilverBulletClient(server.url).list_markdown_files()
    assert server.login_count == 0
    assert server.auth_headers == [None]


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
