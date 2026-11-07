"""Keeps a cached view of all paper-window pages on the SilverBullet server."""

from __future__ import annotations

import logging

from .pages import PaperPage, extract_tasks, make_page, toggle_task_line
from .silverbullet import SilverBulletClient, SilverBulletError

log = logging.getLogger(__name__)


class PageIndex:
    def __init__(self, client: SilverBulletClient, tag: str):
        self._client = client
        self._tag = tag
        # path -> (lastModified, page or None when the tag is absent)
        self._cache: dict[str, tuple[int | None, PaperPage | None]] = {}

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
                    page = make_page(remote.name, self._client.read_page(remote.name), self._tag)
                except SilverBulletError as exc:
                    log.warning("skipping %s: %s", remote.name, exc)
                    continue
                self._cache[remote.name] = (remote.last_modified, page)
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
        fresh_text = self._client.read_page(page.path)
        new_text = toggle_task_line(fresh_text, task.line_index, task.text)
        self._client.write_page(page.path, new_text)
        self._cache.pop(page.path, None)
        updated = make_page(page.path, new_text, self._tag)
        if updated is None:
            # Tag was removed while the page was open; keep showing the edited text.
            updated = PaperPage(page.path, page.name, new_text, extract_tasks(new_text))
        return updated
