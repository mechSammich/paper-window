"""Main event loop: applies button actions, refreshes from the server and redraws the panel."""

from __future__ import annotations

import logging
import queue
import time

from .buttons import Action
from .display import Display
from .pages import PaperPage, StaleTaskError, group_tasks_by_first_tag
from .render import Renderer
from .silverbullet import SilverBulletError
from .state import Browser
from .sync import PageIndex

log = logging.getLogger(__name__)

POLL_SECONDS = 0.2
INACTIVITY_SECONDS = 10 * 60


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
        self._source_pages: list[PaperPage] = []
        self._message: str | None = None

    def run(self) -> None:
        self._display.show(self._renderer.render_screensaver())
        self._refresh()
        next_refresh = time.monotonic() + self._refresh_seconds
        last_activity = time.monotonic()
        screensaver = True
        while True:
            try:
                action = self._events.get(timeout=POLL_SECONDS)
            except queue.Empty:
                action = None

            if action is Action.QUIT:
                return
            if action is not None:
                last_activity = time.monotonic()
                if screensaver:
                    screensaver = False
                else:
                    self._handle(action)
                self._draw()
            now = time.monotonic()
            if not screensaver and now - last_activity >= INACTIVITY_SECONDS:
                self._display.show(self._renderer.render_screensaver())
                screensaver = True
            if now >= next_refresh:
                self._refresh()
                if not screensaver:
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
        task = self._browser.selected_task
        if task is None:
            self._message = "No task to toggle"
            return
        page = next(page for page in self._source_pages if page.path == task.source_path)
        task_index = next(
            index for index, source_task in enumerate(page.tasks)
            if source_task.line_index == task.line_index and source_task.text == task.text
        )
        try:
            updated = self._index.toggle(page, task_index)
        except StaleTaskError:
            self._message = "Task changed; refreshing"
            self._refresh()
        except SilverBulletError as exc:
            log.error("toggle failed: %s", exc)
            self._message = "Save failed (offline?)"
        else:
            self._source_pages = [
                updated if source.path == updated.path else source for source in self._source_pages
            ]
            self._browser.set_pages(group_tasks_by_first_tag(self._source_pages))

    def _refresh(self) -> None:
        try:
            pages = self._index.refresh()
        except SilverBulletError as exc:
            log.warning("refresh failed: %s", exc)
            self._message = "Offline; showing last data"
            return
        self._source_pages = pages
        self._browser.set_pages(group_tasks_by_first_tag(pages))

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
