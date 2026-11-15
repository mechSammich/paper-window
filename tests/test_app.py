import queue

import pytest
from PIL import ImageDraw, ImageFont

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


def test_replace_page_keeps_selected_task_when_completion_reorders_it():
    browser = Browser()
    before = make_page("Tasks.md", f"---\ntags: [{TAG}]\n---\n- [ ] first\n- [ ] second\n", TAG)
    after = make_page("Tasks.md", f"---\ntags: [{TAG}]\n---\n- [x] first\n- [ ] second\n", TAG)
    browser.set_pages([before])

    browser.replace_page(after)
    assert browser.task_index == 1
    assert browser.selected_task.text == "first"

    browser.replace_page(before)
    assert browser.task_index == 0
    assert browser.selected_task.text == "first"


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


@pytest.mark.parametrize(
    ("task_text", "selected", "expected"),
    [("- [ ] one\n- [x] two", 0, "1/2"), ("- [ ] one\n- [x] two", 1, "2/2"), ("", 0, "0/0")],
)
def test_renderer_header_shows_task_and_page_positions(monkeypatch, task_text, selected, expected):
    renderer = Renderer(load_font("", 15), chars_per_row=26)
    task_page = make_page("Tasks.md", f"---\ntags: [{TAG}]\n---\n{task_text}\n", TAG)
    drawn = []
    original_text = ImageDraw.ImageDraw.text

    def record_text(draw, xy, text, *args, **kwargs):
        if xy[1] == 1:
            drawn.append((xy, text))
        return original_text(draw, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", record_text)
    renderer.render(task_page, 2, 3, selected, 0)

    assert [text for _, text in drawn] == [f"Tasks {expected}", "page 2/3"]


def test_renderer_truncates_long_page_name_before_header_positions(monkeypatch):
    font = load_font("", 15)
    renderer = Renderer(font, chars_per_row=26)
    drawn = []
    original_text = ImageDraw.ImageDraw.text

    def record_text(draw, xy, text, *args, **kwargs):
        if xy[1] == 1:
            drawn.append((xy, text))
        return original_text(draw, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", record_text)
    renderer.render(page("A very long page name that cannot fit", ["one", "two"]), 2, 3, 1, 0)

    assert drawn[0][1].endswith("... 2/2")
    assert drawn[1][1] == "page 2/3"
    assert drawn[0][0][0] + font.getlength(drawn[0][1]) < drawn[1][0][0]


def test_renderer_uses_inverse_header_selection_and_status_bar():
    renderer = Renderer(load_font("", 15), chars_per_row=26)
    image, _ = renderer.render(page("Groceries", ["milk", "eggs"]), 1, 2, 1, 0, "Offline")
    footer_y = renderer.height - renderer.line_height
    selected_y = renderer.body_top + renderer.line_height

    assert image.getpixel((0, 0)) == 0
    assert image.getpixel((0, renderer.body_top)) == 255
    assert image.getpixel((0, selected_y)) == 0
    assert image.getpixel((0, footer_y)) == 0
    assert image.crop((0, footer_y, renderer.width, renderer.height)).getbbox()


def test_renderer_draws_completed_task_checkbox():
    renderer = Renderer(load_font("", 15), chars_per_row=26)
    open_page = page("Tasks", ["done"])
    done_page = make_page(
        "Tasks.md",
        f"---\ntags: [{TAG}]\n---\n- [x] done\n",
        TAG,
    )
    open_image, _ = renderer.render(open_page, 1, 1, 0, 0)
    done_image, _ = renderer.render(done_page, 1, 1, 0, 0)
    checkbox = (0, renderer.body_top, 20, renderer.body_top + renderer.line_height)

    assert open_image.crop(checkbox).tobytes() != done_image.crop(checkbox).tobytes()


def test_renderer_hides_silverbullet_tags_from_task_text():
    renderer = Renderer(load_font("", 15), chars_per_row=26)
    tagged_page = page("Tasks", ["Review #work #project/nested"])
    clean_page = page("Tasks", ["Review"])

    tagged_image, _ = renderer.render(tagged_page, 1, 1, 0, 0)
    clean_image, _ = renderer.render(clean_page, 1, 1, 0, 0)

    assert tagged_image.tobytes() == clean_image.tobytes()


def test_renderer_hides_task_modifiers():
    renderer = Renderer(load_font("", 15), chars_per_row=26)
    modified_page = page("Tasks", ["Review [due: 2026-11-15] #work [priority: high]"])
    clean_page = page("Tasks", ["Review"])

    modified_image, _ = renderer.render(modified_page, 1, 1, 0, 0)
    clean_image, _ = renderer.render(clean_page, 1, 1, 0, 0)

    assert modified_image.tobytes() == clean_image.tobytes()


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
