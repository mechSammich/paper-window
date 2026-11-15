import queue

import pytest
from PIL import Image, ImageDraw, ImageFont

from paper_window.buttons import Action
from paper_window.pages import make_page
from paper_window.render import Renderer, load_font, visible_range, wrap_task
from paper_window.state import Browser

TAG = "paper-window"


def page(name, tasks):
    body = "\n".join(f"- [ ] {t}" for t in tasks)
    return make_page(f"{name}.md", f"---\ntags: [{TAG}]\n---\n{body}\n", TAG)


def test_browser_navigation_wraps_pages_and_clamps_tasks():
    browser = Browser()
    browser.set_pages([page("A", ["a1", "a2"]), page("B", []), page("C", ["c1"])])
    assert browser.current_page.name == "A"
    browser.next_task()
    browser.next_task()
    assert browser.selected_task.text == "a2"
    browser.next_page()
    assert browser.current_page.name == "B" and browser.selected_task is None
    browser.next_page()
    browser.next_page()
    assert browser.current_page.name == "A" and browser.task_index == 0
    browser.prev_page()
    assert browser.current_page.name == "C"


def test_set_pages_keeps_current_page_selected():
    browser = Browser()
    browser.set_pages([page("A", ["x"]), page("B", ["y", "z"])])
    browser.next_page()
    browser.next_task()
    browser.set_pages([page("Z", ["q"]), page("B", ["y"])])
    assert browser.current_page.name == "B"
    assert browser.task_index == 0  # clamped to the shorter list


def test_replace_page_updates_matching_path():
    browser = Browser()
    browser.set_pages([page("A", ["x"])])
    browser.replace_page(page("A", ["x", "new"]))
    assert len(browser.current_page.tasks) == 2


def test_wrap_task_limits_row_width():
    lines = wrap_task("buy oat milk and two loaves of sourdough bread from the shop", 22)
    assert all(len(line) <= 22 for line in lines)
    assert " ".join(lines) == "buy oat milk and two loaves of sourdough bread from the shop"


def test_visible_range_keeps_selection_on_screen():
    counts = [2, 2, 2, 2, 2]
    assert visible_range(counts, 0, 0, capacity=4) == 0
    assert visible_range(counts, 4, 0, capacity=4) == 3
    assert visible_range(counts, 1, 3, capacity=4) == 1
    assert visible_range([], 0, 0, capacity=4) == 0


def test_renderer_produces_1bit_frame_of_display_size():
    renderer = Renderer(load_font("", 15), chars_per_row=26)
    image, top = renderer.render(page("Groceries", ["milk", "eggs"]), 1, 2, 1, 0)
    assert image.mode == "1"
    assert image.size == (250, 122)
    assert top == 0


def test_renderer_handles_empty_states():
    renderer = Renderer(load_font("", 15), chars_per_row=26)
    assert renderer.render(None, 0, 0, 0, 0)[0].size == (250, 122)
    assert renderer.render(page("Empty", []), 1, 1, 0, 0)[0].size == (250, 122)
    assert renderer.render(None, 0, 0, 0, 0, message="Offline")[0].size == (250, 122)


def test_screensaver_is_white_with_only_the_title():
    renderer = Renderer(load_font("", 15), chars_per_row=26)
    expected = Image.new("1", (250, 122), 255)
    ImageDraw.Draw(expected).text((2, 0), "paper window", font=renderer.font, fill=0)

    image = renderer.render_screensaver()
    assert image.mode == "1"
    assert image.size == (250, 122)
    assert image.tobytes() == expected.tobytes()


def test_screensaver_startup_inactivity_and_wake(monkeypatch):
    from paper_window.app import PaperWindowApp

    clock = [0.0]
    monkeypatch.setattr("paper_window.app.time.monotonic", lambda: clock[0])
    renderer = Renderer(load_font("", 15), 26)
    splash = renderer.render_screensaver().tobytes()
    frames = []
    refreshes = []
    toggles = []
    current_page = page("A", ["first", "second"])

    class Display:
        def show(self, image):
            frames.append((clock[0], image.tobytes()))

    class Index:
        def refresh(self):
            if not refreshes:
                assert frames == [(0.0, splash)]
            refreshes.append(clock[0])
            return [current_page]

        def toggle(self, selected_page, task_index):
            toggles.append((clock[0], task_index))
            return selected_page

    class Events:
        actions = iter([
            (0, Action.NEXT_TASK),
            (100, Action.NEXT_TASK),
            (699.9, None),
            (700, None),
            (800, None),
            (801, Action.TOGGLE_TASK),
            (802, Action.TOGGLE_TASK),
            (803, Action.QUIT),
        ])

        def get(self, timeout):
            clock[0], action = next(self.actions)
            if action is None:
                raise queue.Empty
            return action

    app = PaperWindowApp(Index(), renderer, Display(), Events(), 60)
    app.run()

    assert [time for time, frame in frames if frame == splash] == [0, 700]
    assert 800 in refreshes
    assert all(time != 800 for time, _ in frames)
    assert toggles == [(802, 1)]


def test_default_font_fits_about_26_characters_per_row():
    font = load_font("", 15)
    if isinstance(font, ImageFont.ImageFont):
        pytest.skip("no TrueType monospace font installed")
    assert font.getlength("W" * 26) <= 250


def test_load_font_reports_missing_font():
    with pytest.raises(FileNotFoundError):
        load_font("/nonexistent/font.ttf", 15)


def test_app_toggles_task_and_redraws(tmp_path):
    from paper_window.app import PaperWindowApp
    from paper_window.display import SimulatedDisplay
    from paper_window.sync import PageIndex
    from tests.test_silverbullet import FakeSilverBullet, client_for
    import threading
    from http.server import ThreadingHTTPServer

    fake = FakeSilverBullet()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), fake.handler())
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    fake.url = f"http://127.0.0.1:{httpd.server_port}"
    try:
        index = PageIndex(client_for(fake), TAG)
        out = tmp_path / "frame.png"
        app = PaperWindowApp(index, Renderer(load_font("", 15), 26), SimulatedDisplay(out), queue.Queue(), 60)
        app._refresh()
        app._handle(Action.TOGGLE_TASK)
        app._draw()
        assert fake.files["Work/Inbox.md"]["text"].count("- [x] first") == 1
        assert out.exists()
        app._handle(Action.NEXT_TASK)
        assert app._browser.selected_task.text == "second"
    finally:
        httpd.shutdown()
        httpd.server_close()
