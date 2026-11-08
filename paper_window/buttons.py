"""Input backends: GPIO push buttons on the Pi, or stdin keys for simulation."""

from __future__ import annotations

import logging
import queue
import sys
import threading
from enum import Enum
from functools import partial

from .config import ButtonConfig

log = logging.getLogger(__name__)


class Action(Enum):
    NEXT_TASK = "next_task"
    PREV_TASK = "prev_task"
    TOGGLE_TASK = "toggle_task"
    NEXT_PAGE = "next_page"
    PREV_PAGE = "prev_page"
    QUIT = "quit"


class GpioButtons:
    def __init__(self, pins: ButtonConfig, events: queue.Queue):
        from gpiozero import Button

        mapping = {
            Action.NEXT_TASK: pins.next_task,
            Action.PREV_TASK: pins.prev_task,
            Action.TOGGLE_TASK: pins.toggle_task,
            Action.NEXT_PAGE: pins.next_page,
            Action.PREV_PAGE: pins.prev_page,
        }
        self._buttons = []
        for action, pin in mapping.items():
            button = Button(pin, pull_up=True, bounce_time=pins.bounce_seconds)
            button.when_pressed = partial(events.put, action)
            self._buttons.append(button)

    def close(self) -> None:
        for button in self._buttons:
            button.close()


KEY_ACTIONS = {
    "j": Action.NEXT_TASK,
    "k": Action.PREV_TASK,
    "": Action.TOGGLE_TASK,  # bare Enter
    "n": Action.NEXT_PAGE,
    "p": Action.PREV_PAGE,
    "q": Action.QUIT,
}


class KeyboardButtons:
    """Reads one-letter commands from stdin: j/k tasks, Enter toggle, n/p pages, q quit."""

    def __init__(self, events: queue.Queue, stream=None):
        self._events = events
        self._stream = stream or sys.stdin
        self._thread = threading.Thread(target=self._run, name="keyboard-buttons", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        for line in self._stream:
            key = line.strip().lower()[:1]
            action = KEY_ACTIONS.get(key)
            if action is None:
                log.info("unknown key %r (j/k tasks, Enter toggle, n/p pages, q quit)", key)
                continue
            self._events.put(action)
            if action is Action.QUIT:
                return

    def close(self) -> None:
        return None
