import pytest

from paper_window.config import ConfigError, load_config, parse_config


def minimal(**server_overrides):
    server = {"url": "http://localhost:3000"}
    server.update(server_overrides)
    return {"server": server}


def test_defaults_applied():
    config = parse_config(minimal())
    assert config.server.tag == "paper-window"
    assert config.display.chars_per_row == 26
    assert config.buttons.next_task == 5


def test_url_is_required_and_must_be_http():
    with pytest.raises(ConfigError, match="url is required"):
        parse_config({"server": {}})
    with pytest.raises(ConfigError, match="http"):
        parse_config(minimal(url="ftp://example.com"))


def test_password_requires_username_unless_token_is_set():
    with pytest.raises(ConfigError, match="username is required"):
        parse_config(minimal(password="secret"))
    assert parse_config(minimal(password="secret", token="token")).server.token == "token"


def test_unknown_keys_are_rejected():
    with pytest.raises(ConfigError, match="unknown key"):
        parse_config(minimal(urll="http://x"))


def test_duplicate_button_pins_are_rejected():
    with pytest.raises(ConfigError, match="different"):
        parse_config({**minimal(), "buttons": {"next_task": 5, "prev_task": 5}})


def test_load_config_from_toml(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[server]\nurl = "http://pi.local:3000"\nusername = "u"\npassword = "p"\n')
    config = load_config(path)
    assert config.server.username == "u"
    assert config.server.password == "p"


def test_load_config_reports_missing_and_invalid_files(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.toml")
    bad = tmp_path / "bad.toml"
    bad.write_text("[server\n")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(bad)
