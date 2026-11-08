"""Display backends: the Waveshare 2.13" V4 e-paper panel, or a PNG file for simulation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from PIL import Image

from .render import DISPLAY_HEIGHT, DISPLAY_WIDTH

log = logging.getLogger(__name__)


class Display(Protocol):
    def show(self, image: Image.Image) -> None: ...

    def close(self) -> None: ...


class EpdDisplay:
    """Drives the panel via Waveshare's epd2in13_V4 module (install from their Raspberry Pi library)."""

    def __init__(self) -> None:
        from waveshare_epd import epd2in13_V4

        self._epd = epd2in13_V4.EPD()

    def show(self, image: Image.Image) -> None:
        # The driver rotates landscape frames internally, so pass the 250x122 image directly.
        self._epd.init()
        self._epd.display(self._epd.getbuffer(image))
        self._epd.sleep()

    def close(self) -> None:
        from waveshare_epd import epdconfig

        try:
            self._epd.init()
            self._epd.Clear(0xFF)
            self._epd.sleep()
        finally:
            epdconfig.module_exit(cleanup=True)


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
