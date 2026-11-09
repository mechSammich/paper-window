"""Configuration loading from a TOML file."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Raspberry Pi OS Bullseye ships Python 3.9
    import tomli as tomllib


class ConfigError(Exception):
    """The configuration file is missing or invalid."""


@dataclass(frozen=True)
class ServerConfig:
    url: str
    username: str = ""
    password: str = ""
    token: str = ""
    tag: str = "paper-window"
    refresh_seconds: int = 300
    timeout_seconds: float = 10.0


@dataclass(frozen=True)
class DisplayConfig:
    font_path: str = ""
    font_size: int = 15
    chars_per_row: int = 26


@dataclass(frozen=True)
class ButtonConfig:
    next_task: int = 5
    prev_task: int = 6
    toggle_task: int = 13
    next_page: int = 19
    prev_page: int = 26
    bounce_seconds: float = 0.05


@dataclass(frozen=True)
class Config:
    server: ServerConfig
    display: DisplayConfig = field(default_factory=DisplayConfig)
    buttons: ButtonConfig = field(default_factory=ButtonConfig)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"[{name}] must be a table")
    return value


def _build(cls, section: dict[str, Any], name: str):
    known = {f for f in cls.__dataclass_fields__}
    unknown = set(section) - known
    if unknown:
        raise ConfigError(f"unknown key(s) in [{name}]: {', '.join(sorted(unknown))}")
    try:
        return cls(**section)
    except TypeError as exc:
        raise ConfigError(f"invalid [{name}] section: {exc}") from exc


def parse_config(data: dict[str, Any]) -> Config:
    server_data = _section(data, "server")
    if "url" not in server_data:
        raise ConfigError("[server] url is required")
    server = _build(ServerConfig, server_data, "server")
    if not server.url.startswith(("http://", "https://")):
        raise ConfigError("[server] url must start with http:// or https://")
    if server.password and not server.username and not server.token:
        raise ConfigError("[server] username is required when password is set")
    if server.refresh_seconds < 1:
        raise ConfigError("[server] refresh_seconds must be at least 1")

    display = _build(DisplayConfig, _section(data, "display"), "display")
    if display.chars_per_row < 8:
        raise ConfigError("[display] chars_per_row must be at least 8")

    buttons = _build(ButtonConfig, _section(data, "buttons"), "buttons")
    pins = [buttons.next_task, buttons.prev_task, buttons.toggle_task, buttons.next_page, buttons.prev_page]
    if len(set(pins)) != len(pins):
        raise ConfigError("[buttons] GPIO pins must all be different")

    return Config(server=server, display=display, buttons=buttons)


def load_config(path: str | Path) -> Config:
    path = Path(path)
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from exc
    return parse_config(data)
