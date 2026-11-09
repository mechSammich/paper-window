"""Command line entry point: `python -m paper_window --config config.toml`."""

from __future__ import annotations

import argparse
import logging
import queue
import sys

from .app import PaperWindowApp
from .buttons import GpioButtons, KeyboardButtons
from .config import ConfigError, load_config
from .display import EpdDisplay, SimulatedDisplay
from .render import Renderer, load_font
from .silverbullet import SilverBulletClient
from .sync import PageIndex


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paper-window", description="E-paper view of SilverBullet tasks")
    parser.add_argument("-c", "--config", default="config.toml", help="path to the TOML config file")
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="run without hardware: write frames to a PNG and read commands from stdin",
    )
    parser.add_argument(
        "--simulate-output",
        default="simulated-display.png",
        help="PNG file written in simulation mode",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        config = load_config(args.config)
        font = load_font(config.display.font_path, config.display.font_size)
    except (ConfigError, OSError) as exc:
        print(f"paper-window: {exc}", file=sys.stderr)
        return 2

    client = SilverBulletClient(
        config.server.url,
        username=config.server.username,
        password=config.server.password,
        token=config.server.token,
        timeout=config.server.timeout_seconds,
    )
    index = PageIndex(client, config.server.tag)
    renderer = Renderer(font, config.display.chars_per_row)
    events: queue.Queue = queue.Queue()

    if args.simulate:
        display = SimulatedDisplay(args.simulate_output)
        inputs = KeyboardButtons(events)
        inputs.start()
    else:
        display = EpdDisplay()
        inputs = GpioButtons(config.buttons, events)

    app = PaperWindowApp(index, renderer, display, events, config.server.refresh_seconds)
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        inputs.close()
        display.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
