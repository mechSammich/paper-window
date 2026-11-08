"""Renders the current page and task list into a 1-bit image for the e-paper panel."""

from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .pages import PaperPage

DISPLAY_WIDTH = 250
DISPLAY_HEIGHT = 122
CHECKBOX_CHARS = 4  # "[ ] " / "[x] "

DEFAULT_FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
)


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if path:
        if not Path(path).is_file():
            raise FileNotFoundError(f"font not found: {path}")
        return ImageFont.truetype(path, size)
    for candidate in DEFAULT_FONT_PATHS:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    try:
        return ImageFont.load_default(size)
    except TypeError:  # Pillow < 10.1 has no sized default font
        return ImageFont.load_default()


def wrap_task(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width, break_long_words=True, break_on_hyphens=False) or [""]


def visible_range(row_counts: list[int], selected: int, top: int, capacity: int) -> int:
    """Return the first task index to draw so the selected task fits on screen."""
    if not row_counts:
        return 0
    selected = min(selected, len(row_counts) - 1)
    top = max(0, min(top, selected))
    while top < selected and sum(row_counts[top : selected + 1]) > capacity:
        top += 1
    return top


class Renderer:
    def __init__(self, font, chars_per_row: int, width: int = DISPLAY_WIDTH, height: int = DISPLAY_HEIGHT):
        self.font = font
        self.width = width
        self.height = height
        self.text_chars = chars_per_row - CHECKBOX_CHARS
        ascent, descent = font.getmetrics()
        self.line_height = ascent + descent + 2
        self.body_top = self.line_height + 3

    def render(
        self,
        page: PaperPage | None,
        page_number: int,
        page_count: int,
        selected: int,
        scroll_top: int,
        message: str | None = None,
    ) -> tuple[Image.Image, int]:
        """Return the frame and the scroll offset actually used."""
        image = Image.new("1", (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)
        footer_h = self.line_height if message else 0
        capacity = (self.height - self.body_top - footer_h) // self.line_height

        if page is None:
            self._header(draw, "paper-window", "")
            self._body_message(draw, message or "No tagged pages found", self.body_top)
            return image, 0

        self._header(draw, page.name, f"{page_number}/{page_count}")
        if not page.tasks:
            self._body_message(draw, "No tasks on this page", self.body_top)
            self._footer(draw, message)
            return image, 0

        rows = [wrap_task(task.text, self.text_chars)[:capacity] for task in page.tasks]
        top = visible_range([len(r) for r in rows], selected, scroll_top, capacity)

        y = self.body_top
        for index in range(top, len(rows)):
            lines = rows[index]
            block_height = len(lines) * self.line_height
            if y + block_height > self.height - footer_h:
                break
            task = page.tasks[index]
            is_selected = index == selected
            if is_selected:
                draw.rectangle((0, y, self.width - 1, y + block_height - 1), fill=0)
            ink = 255 if is_selected else 0
            prefix = "[x] " if task.done else "[ ] "
            indent = draw.textlength(prefix, font=self.font)
            for line_no, line in enumerate(lines):
                line_y = y + line_no * self.line_height
                if line_no == 0:
                    draw.text((2, line_y), prefix + line, font=self.font, fill=ink)
                else:
                    draw.text((2 + indent, line_y), line, font=self.font, fill=ink)
            y += block_height

        self._footer(draw, message)
        return image, top

    def _header(self, draw: ImageDraw.ImageDraw, title: str, right: str) -> None:
        right_w = draw.textlength(right, font=self.font) if right else 0
        room = self.width - right_w - 8
        while title and draw.textlength(title, font=self.font) > room:
            title = title[:-1]
        draw.text((2, 0), title, font=self.font, fill=0)
        if right:
            draw.text((self.width - right_w - 2, 0), right, font=self.font, fill=0)
        draw.line((0, self.line_height, self.width, self.line_height), fill=0)

    def _body_message(self, draw: ImageDraw.ImageDraw, text: str, y: int) -> None:
        for offset, line in enumerate(wrap_task(text, self.text_chars + CHECKBOX_CHARS)):
            draw.text((2, y + offset * self.line_height), line, font=self.font, fill=0)

    def _footer(self, draw: ImageDraw.ImageDraw, message: str | None) -> None:
        if not message:
            return
        y = self.height - self.line_height
        draw.rectangle((0, y, self.width - 1, self.height - 1), fill=255)
        draw.line((0, y, self.width, y), fill=0)
        text = message
        while text and draw.textlength(text, font=self.font) > self.width - 4:
            text = text[:-1]
        draw.text((2, y + 1), text, font=self.font, fill=0)
