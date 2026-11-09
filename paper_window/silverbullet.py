"""Minimal client for the SilverBullet /.fs HTTP API."""

from __future__ import annotations

import http.cookiejar
import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

log = logging.getLogger(__name__)


class SilverBulletError(Exception):
    """A request to the SilverBullet server failed."""


class _AuthenticationError(SilverBulletError):
    """The server rejected a request or redirected it to a login page."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


@dataclass(frozen=True)
class RemoteFile:
    name: str
    last_modified: int | None


class SilverBulletClient:
    def __init__(
        self, base_url: str, username: str = "", password: str = "", timeout: float = 10.0,
        token: str = "",
    ):
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._username = username
        self._password = password
        self._cookie_mode = bool(username) and not token
        self._logged_in = False
        self._cookies = http.cookiejar.CookieJar()
        self._opener = build_opener(_NoRedirect(), HTTPCookieProcessor(self._cookies))
        self._headers = {"User-Agent": "paper-window/1", "X-Sync-Mode": "true"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def _url(self, name: str = "") -> str:
        if not name:
            return f"{self._base}/.fs"
        return f"{self._base}/.fs/{quote(name, safe='/')}"

    def _send(
        self, method: str, url: str, body: bytes | None = None, content_type: str = ""
    ) -> bytes:
        headers = dict(self._headers)
        if content_type:
            headers["Content-Type"] = content_type
        request = Request(url, data=body, method=method, headers=headers)
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                return response.read()
        except HTTPError as exc:
            if 300 <= exc.code < 400 or exc.code in (401, 403):
                raise _AuthenticationError(f"{method} {url} failed: HTTP {exc.code}") from exc
            raise SilverBulletError(f"{method} {url} failed: HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise SilverBulletError(f"{method} {url} failed: {exc}") from exc

    def _login(self) -> None:
        self._logged_in = False
        self._cookies.clear()
        body = urlencode({"username": self._username, "password": self._password}).encode("utf-8")
        raw = self._send("POST", f"{self._base}/.auth", body, "application/x-www-form-urlencoded")
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise SilverBulletError("SilverBullet login returned invalid JSON") from exc
        if not isinstance(result, dict) or result.get("status") != "ok":
            raise SilverBulletError("SilverBullet login failed; check credentials and server authentication")
        self._logged_in = True

    def _request(self, method: str, url: str, body: bytes | None = None) -> bytes:
        if self._cookie_mode and not self._logged_in:
            self._login()
        content_type = "text/markdown; charset=utf-8" if body is not None else ""
        try:
            return self._send(method, url, body, content_type)
        except _AuthenticationError:
            if not self._cookie_mode:
                raise
            self._login()
            return self._send(method, url, body, content_type)

    def list_markdown_files(self) -> list[RemoteFile]:
        raw = self._request("GET", self._url())
        try:
            entries = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise SilverBulletError("file listing was not valid JSON") from exc
        files = []
        for entry in entries:
            name = entry.get("name", "")
            if not name.endswith(".md"):
                continue
            # Skip SilverBullet internals and hidden folders such as _plug or .git
            if any(part.startswith((".", "_")) for part in name.split("/")):
                continue
            files.append(RemoteFile(name=name, last_modified=entry.get("lastModified")))
        return files

    def read_page(self, path: str) -> str:
        return self._request("GET", self._url(path)).decode("utf-8")

    def write_page(self, path: str, text: str) -> None:
        self._request("PUT", self._url(path), body=text.encode("utf-8"))
