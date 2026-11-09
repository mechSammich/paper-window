"""Display backends: the Waveshare 2.13" V4 e-paper panel, or a PNG file for simulation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from PIL import Image

from .render import DISPLAY_HEIGHT, DISPLAY_WIDTH

log = logging.getLogger(__name__)

MAX_PARTIAL_REFRESHES = 10


class Display(Protocol):
    def show(self, image: Image.Image) -> None: ...

    def close(self) -> None: ...


class EpdDisplay:
    """Drives the panel via Waveshare's epd2in13_V4 module (install from their Raspberry Pi library)."""

    def __init__(self) -> None:
        from waveshare_epd import epd2in13_V4

        self._epd = epd2in13_V4.EPD()
        self._initialized = False
        self._last_frame: tuple[tuple[int, int], bytes] | None = None
        self._partial_refreshes = 0

    def show(self, image: Image.Image) -> None:
        # The driver rotates landscape frames internally, so pass the 250x122 image directly.
        frame = image.convert("1")
        key = (frame.size, frame.tobytes())
        if key == self._last_frame:
            return

        buffer = self._epd.getbuffer(frame)
        if not self._initialized:
            if self._epd.init_fast() != 0:
                raise RuntimeError("failed to initialize e-paper display")
            self._initialized = True
            self._epd.displayPartBaseImage(buffer)
            self._partial_refreshes = 0
        elif self._partial_refreshes >= MAX_PARTIAL_REFRESHES:
            self._epd.displayPartBaseImage(buffer)
            self._partial_refreshes = 0
        else:
            self._epd.displayPartial(buffer)
            self._partial_refreshes += 1
        self._last_frame = key

    def close(self) -> None:
        if self._initialized:
            self._epd.sleep()
            self._initialized = False


class SimulatedDisplay:
    """Writes each frame to a PNG so the UI can be checked without hardware."""

    def __init__(self, output: str | Path = "simulated-display.png") -> None:
        self._output = Path(output)
        self.width = DISPLAY_WIDTH
        self.height = DISPLAY_HEIGHT

    def show(self, image: Image.Image) -> None:
        image.save(self._output)
        log.info("frame written to %s", self._output)

    def close(self) -> None:
        return None
