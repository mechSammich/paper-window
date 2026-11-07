import queue

import pytest
from PIL import ImageFont

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
