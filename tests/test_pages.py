import pytest

from paper_window.pages import (
    StaleTaskError,
    extract_tasks,
    has_tag,
    make_page,
    parse_frontmatter,
    toggle_task_line,
)

PAGE = """---
tags: [paper-window, project]
---
# Groceries

- [ ] buy milk
* [x] pick up parcel
  - [ ] nested item
Not a task
- [X] shouted done
"""


def test_frontmatter_tags_as_list_and_string():
    assert has_tag(parse_frontmatter(PAGE), "paper-window")
    assert has_tag({"tags": "notes, paper-window"}, "paper-window")
    assert has_tag({"tags": ["#Paper-Window"]}, "paper-window")
    assert not has_tag({"tags": ["other"]}, "paper-window")
    assert not has_tag({}, "paper-window")


def test_invalid_frontmatter_is_ignored():
    assert parse_frontmatter("---\ntags: [unclosed\n---\nbody") == {}
    assert parse_frontmatter("no frontmatter here") == {}


def test_extract_tasks_reports_line_index_and_state():
    tasks = extract_tasks(PAGE)
    assert [(t.line_index, t.text, t.done) for t in tasks] == [
        (5, "buy milk", False),
        (6, "pick up parcel", True),
        (7, "nested item", False),
        (9, "shouted done", True),
    ]


def test_frontmatter_lines_are_not_tasks():
    text = "---\ntags: [paper-window]\nitems:\n  - [ ] fake\n---\n- [ ] real\n"
    assert [t.text for t in extract_tasks(text)] == ["real"]


def test_make_page_requires_tag():
    assert make_page("Shopping.md", PAGE, "paper-window").name == "Shopping"
    assert make_page("Plain.md", "- [ ] nope", "paper-window") is None


def test_toggle_task_line_round_trips():
    once = toggle_task_line(PAGE, 5, "buy milk")
    assert "- [x] buy milk" in once.split("\n")
    twice = toggle_task_line(once, 5, "buy milk")
    assert twice == PAGE


def test_toggle_preserves_crlf_line_endings():
    text = "---\r\ntags: [paper-window]\r\n---\r\n- [ ] milk\r\n"
    assert toggle_task_line(text, 3, "milk") == "---\r\ntags: [paper-window]\r\n---\r\n- [x] milk\r\n"


def test_toggle_rejects_changed_task():
    with pytest.raises(StaleTaskError):
        toggle_task_line(PAGE, 5, "something else")
    with pytest.raises(StaleTaskError):
        toggle_task_line(PAGE, 0, "buy milk")
    with pytest.raises(StaleTaskError):
        toggle_task_line(PAGE, 500, "buy milk")
