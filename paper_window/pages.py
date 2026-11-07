"""Pure helpers for SilverBullet page content: frontmatter, tags and tasks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml

FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
TASK_RE = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s*(.*?)\s*$")
TASK_STATE_RE = re.compile(r"^(\s*[-*+]\s+\[)([ xX])(\])")


class StaleTaskError(Exception):
    """The task at a given line no longer matches what was displayed."""


@dataclass(frozen=True)
class Task:
    line_index: int
    text: str
    done: bool


@dataclass(frozen=True)
class PaperPage:
    path: str
    name: str
    text: str
    tasks: tuple[Task, ...]


def parse_frontmatter(text: str) -> dict[str, Any]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def has_tag(frontmatter: dict[str, Any], tag: str) -> bool:
    tags = frontmatter.get("tags")
    if isinstance(tags, str):
        tags = [part for part in re.split(r"[,\s]+", tags) if part]
    if not isinstance(tags, list):
        return False
    wanted = tag.lstrip("#").lower()
    return any(str(item).strip().lstrip("#").lower() == wanted for item in tags)


def _body_start(text: str) -> int:
    """Return the line index where the page body (after frontmatter) starts."""
    match = FRONTMATTER_RE.match(text)
    return match.group(0).count("\n") if match else 0


def extract_tasks(text: str) -> tuple[Task, ...]:
    lines = text.split("\n")
    tasks = []
    for index in range(_body_start(text), len(lines)):
        match = TASK_RE.match(lines[index])
        if match:
            tasks.append(Task(index, match.group(2), match.group(1).lower() == "x"))
    return tuple(tasks)


def make_page(path: str, text: str, tag: str) -> PaperPage | None:
    """Return a PaperPage if the markdown carries the tag in its frontmatter."""
    if not has_tag(parse_frontmatter(text), tag):
        return None
    name = path[:-3] if path.endswith(".md") else path
    return PaperPage(path=path, name=name, text=text, tasks=extract_tasks(text))


def toggle_task_line(text: str, line_index: int, expected_text: str) -> str:
    """Flip the checkbox on one task line, verifying it still holds the expected task."""
    lines = text.split("\n")
    if line_index >= len(lines):
        raise StaleTaskError("task line no longer exists")
    match = TASK_RE.match(lines[line_index])
    if not match or match.group(2) != expected_text:
        raise StaleTaskError("task changed since it was displayed")
    new_state = " " if match.group(1).lower() == "x" else "x"
    lines[line_index] = TASK_STATE_RE.sub(
        lambda m: f"{m.group(1)}{new_state}{m.group(3)}", lines[line_index], count=1
    )
    return "\n".join(lines)
