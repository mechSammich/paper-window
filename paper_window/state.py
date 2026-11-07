"""Navigation state for the paper window: which page and task are selected."""

from __future__ import annotations

from dataclasses import dataclass, field

from .pages import PaperPage, Task


@dataclass
class Browser:
    pages: list[PaperPage] = field(default_factory=list)
    page_index: int = 0
    task_index: int = 0
    scroll_top: int = 0

    @property
    def current_page(self) -> PaperPage | None:
        if not self.pages:
            return None
        return self.pages[self.page_index]

    @property
    def selected_task(self) -> Task | None:
        page = self.current_page
        if page is None or not page.tasks:
            return None
        return page.tasks[self.task_index]

    def set_pages(self, pages: list[PaperPage]) -> None:
        """Replace the page list, keeping the current page selected when it still exists."""
        current_path = self.current_page.path if self.current_page else None
        self.pages = pages
        self.page_index = 0
        if current_path is not None:
            for index, page in enumerate(pages):
                if page.path == current_path:
                    self.page_index = index
                    break
        self._clamp_task()

    def replace_page(self, page: PaperPage) -> None:
        for index, existing in enumerate(self.pages):
            if existing.path == page.path:
                self.pages[index] = page
                self._clamp_task()
                return

    def next_page(self) -> None:
        self._move_page(1)

    def prev_page(self) -> None:
        self._move_page(-1)

    def next_task(self) -> None:
        page = self.current_page
        if page and self.task_index < len(page.tasks) - 1:
            self.task_index += 1

    def prev_task(self) -> None:
        if self.task_index > 0:
            self.task_index -= 1

    def _move_page(self, step: int) -> None:
        if not self.pages:
            return
        self.page_index = (self.page_index + step) % len(self.pages)
        self.task_index = 0
        self.scroll_top = 0

    def _clamp_task(self) -> None:
        page = self.current_page
        if page is None or not page.tasks:
            self.task_index = 0
            self.scroll_top = 0
        else:
            self.task_index = min(self.task_index, len(page.tasks) - 1)
