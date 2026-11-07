"""Main event loop: applies button actions, refreshes from the server and redraws the panel."""

from __future__ import annotations

import logging
import queue
import time

from .buttons import Action
from .display import Display
from .pages import StaleTaskError
from .render import Renderer
from .silverbullet import SilverBulletError
from .state import Browser
from .sync import PageIndex

log = logging.getLogger(__name__)

POLL_SECONDS = 0.2


class PaperWindowApp:
    def __init__(
        self,
        index: PageIndex,
        renderer: Renderer,
        display: Display,
        events: queue.Queue,
        refresh_seconds: int,
    ):
        self._index = index
        self._renderer = renderer
        self._display = display
        self._events = events
        self._refresh_seconds = refresh_seconds
        self._browser = Browser()
        self._message: str | None = None

    def run(self) -> None:
        self._refresh()
        self._draw()
        next_refresh = time.monotonic() + self._refresh_seconds
        while True:
            try:
                action = self._events.get(timeout=POLL_SECONDS)
            except queue.Empty:
                action = None

            if action is Action.QUIT:
                return
            if action is not None:
                self._handle(action)
                self._draw()
            if time.monotonic() >= next_refresh:
                self._refresh()
                self._draw()
                next_refresh = time.monotonic() + self._refresh_seconds

    def _handle(self, action: Action) -> None:
        self._message = None
        browser = self._browser
        if action is Action.NEXT_TASK:
            browser.next_task()
        elif action is Action.PREV_TASK:
            browser.prev_task()
        elif action is Action.NEXT_PAGE:
            browser.next_page()
        elif action is Action.PREV_PAGE:
            browser.prev_page()
        elif action is Action.TOGGLE_TASK:
            self._toggle()

    def _toggle(self) -> None:
        page = self._browser.current_page
        if page is None or not page.tasks:
            self._message = "No task to toggle"
            return
        try:
            updated = self._index.toggle(page, self._browser.task_index)
        except StaleTaskError:
            self._message = "Task changed; refreshing"
            self._refresh()
        except SilverBulletError as exc:
            log.error("toggle failed: %s", exc)
            self._message = "Save failed (offline?)"
        else:
            self._browser.replace_page(updated)

    def _refresh(self) -> None:
        try:
            pages = self._index.refresh()
        except SilverBulletError as exc:
            log.warning("refresh failed: %s", exc)
            self._message = "Offline; showing last data"
            return
        self._browser.set_pages(pages)

    def _draw(self) -> None:
        browser = self._browser
        page = browser.current_page
        page_number = browser.page_index + 1
        image, scroll = self._renderer.render(
            page,
            page_number,
            len(browser.pages),
            browser.task_index,
            browser.scroll_top,
            self._message,
        )
        browser.scroll_top = scroll
        self._display.show(image)
