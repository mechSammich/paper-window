import sys
from types import SimpleNamespace

from PIL import Image

from paper_window.display import EpdDisplay, MAX_PARTIAL_REFRESHES


class FakeEpd:
    def __init__(self):
        self.calls = []

    def init_fast(self):
        self.calls.append(("init_fast",))
        return 0

    def getbuffer(self, image):
        return image.tobytes()

    def displayPartBaseImage(self, buffer):
        self.calls.append(("full", buffer))

    def displayPartial(self, buffer):
        self.calls.append(("partial", buffer))

    def sleep(self):
        self.calls.append(("sleep",))


def display_with_fake(monkeypatch):
    epd = FakeEpd()
    driver = SimpleNamespace(EPD=lambda: epd)
    monkeypatch.setitem(sys.modules, "waveshare_epd", SimpleNamespace(epd2in13_V4=driver))
    return EpdDisplay(), epd


def frame(color):
    image = Image.new("1", (250, 122), 255)
    image.putpixel((color % 250, color // 250), 0)
    return image


def test_display_uses_partial_updates_and_periodic_full_refresh(monkeypatch):
    display, epd = display_with_fake(monkeypatch)

    for mark in range(MAX_PARTIAL_REFRESHES + 2):
        display.show(frame(mark))

    assert [call[0] for call in epd.calls] == [
        "init_fast",
        "full",
        *["partial"] * MAX_PARTIAL_REFRESHES,
        "full",
    ]


def test_display_skips_unchanged_frames_and_sleeps_without_clearing(monkeypatch):
    display, epd = display_with_fake(monkeypatch)

    display.show(frame(0))
    display.show(frame(0))
    display.close()

    assert [call[0] for call in epd.calls] == ["init_fast", "full", "sleep"]
