"""Keeps a cached view of all paper-window pages on the SilverBullet server."""

from __future__ import annotations

import logging

from .pages import PaperPage, StaleTaskError, extract_tasks, make_page, toggle_task_line
from .silverbullet import (
    ConditionalWritesUnsupportedError,
    PreconditionFailedError,
    SilverBulletClient,
    SilverBulletError,
)

log = logging.getLogger(__name__)


class PageIndex:
    def __init__(self, client: SilverBulletClient, tag: str):
        self._client = client
        self._tag = tag
        # path -> (lastModified, page or None when the tag is absent, ETag)
        self._cache: dict[str, tuple[int | None, PaperPage | None, str | None]] = {}

    def refresh(self) -> list[PaperPage]:
        """Return all tagged pages, re-reading only files whose lastModified changed."""
        pages: list[PaperPage] = []
        seen: set[str] = set()
        for remote in self._client.list_markdown_files():
            seen.add(remote.name)
            cached = self._cache.get(remote.name)
            if cached and remote.last_modified is not None and cached[0] == remote.last_modified:
                page = cached[1]
            else:
                try:
                    remote_page = self._client.read_page_with_etag(remote.name)
                    page = make_page(remote.name, remote_page.text, self._tag)
                except SilverBulletError as exc:
                    log.warning("skipping %s: %s", remote.name, exc)
                    continue
                self._cache[remote.name] = (remote.last_modified, page, remote_page.etag)
            if page is not None:
                pages.append(page)
        self._cache = {path: value for path, value in self._cache.items() if path in seen}
        pages.sort(key=lambda page: page.name.lower())
        return pages

    def toggle(self, page: PaperPage, task_index: int) -> PaperPage:
        """Flip one task on the server and return the updated page.

        Raises StaleTaskError if the task moved or changed since it was displayed.
        """
        task = page.tasks[task_index]
        remote_page = self._client.read_page_with_etag(page.path)
        new_text = toggle_task_line(remote_page.text, task.line_index, task.text)
        try:
            self._client.write_page(page.path, new_text, if_match=remote_page.etag)
        except PreconditionFailedError as exc:
            self._cache.pop(page.path, None)
            raise StaleTaskError("page changed while the task was being toggled") from exc
        except ConditionalWritesUnsupportedError:
            latest = self._client.read_page_with_etag(page.path)
            if latest.text != remote_page.text:
                self._cache.pop(page.path, None)
                raise StaleTaskError("page changed while conditional writes were unavailable")
            self._client.write_page(page.path, new_text)
        self._cache.pop(page.path, None)
        updated = make_page(page.path, new_text, self._tag)
        if updated is None:
            # Tag was removed while the page was open; keep showing the edited text.
            updated = PaperPage(page.path, page.name, new_text, extract_tasks(new_text))
        return updated
