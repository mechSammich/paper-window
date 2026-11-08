"""Minimal client for the SilverBullet /.fs HTTP API."""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)


class SilverBulletError(Exception):
    """A request to the SilverBullet server failed."""


@dataclass(frozen=True)
class RemoteFile:
    name: str
    last_modified: int | None


class SilverBulletClient:
    def __init__(self, base_url: str, username: str = "", password: str = "", timeout: float = 10.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._headers: dict[str, str] = {}
        if username or password:
            token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
            self._headers["Authorization"] = f"Basic {token}"

    def _url(self, name: str = "") -> str:
        if not name:
            return f"{self._base}/.fs"
        return f"{self._base}/.fs/{quote(name, safe='/')}"

    def _request(self, method: str, url: str, body: bytes | None = None) -> bytes:
        headers = dict(self._headers)
        if body is not None:
            headers["Content-Type"] = "text/markdown; charset=utf-8"
        request = Request(url, data=body, method=method, headers=headers)
        try:
            with urlopen(request, timeout=self._timeout) as response:
                return response.read()
        except HTTPError as exc:
            raise SilverBulletError(f"{method} {url} failed: HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise SilverBulletError(f"{method} {url} failed: {exc}") from exc

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
