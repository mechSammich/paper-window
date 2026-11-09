# paper-window
An e-paper window into the hivemind

# project details
This project allows the user to use a raspberry pi zero w with an e-paper display and a 5 button interface to view and interact with the task items on any local silverbullet note pages that contain the tag "paper-window" in their frontmatter. 

## hardware list
1. raspberry pi zero w v1.1
2. waveshare 2.13" black and white e-paper display hat (V4)
3. tactile button inputs on GPIO for the following functions
   1. next task
   2. previous task
   3. toggle task state
   4. next page
   5. previous page

## software requirements
1. toml config file for easy setup
2. config to contain server url and arguments for password authentication
3. queries target silverbullet server for pages with "paper-window" in frontmatter (tell me if this is not possible)
4. allows user to navigate between pages int this list
5. allows user to scroll through tasks on the current page
6. allows user to toggle task status on selected task
7. displays current page name in upper left of screen
8. font size that allows approximately 26 chars per row

# implementation

## how it works
- Lists every `.md` page on the SilverBullet server (`GET /.fs`) and reads those whose frontmatter `tags` include `paper-window`. Pages are re-read only when their `lastModified` changes.
- Tasks are markdown checkboxes (`- [ ] text` / `- [x] text`). Toggling a task re-reads the page, flips that one line, and writes it back (`PUT /.fs/<page>.md`). When the server supplies an ETag, the write uses `If-Match`; rejected writes are refused and the list refreshes. If ETags or conditional writes are unavailable, the client uses an unconditional write (rechecking the page when conditional writes are explicitly rejected).
- Buttons: next/previous task move the selection (the list scrolls to keep it visible); toggle flips the selected task; next/previous page cycle through the tagged pages.
- The panel is a Waveshare 2.13" V4 (250x122). Text is wrapped to `chars_per_row` (default 26).

## setup (Raspberry Pi)
1. Install Raspberry Pi OS Lite and enable SPI (`sudo raspi-config`).
2. Install the Waveshare e-Paper Raspberry Pi library so `waveshare_epd.epd2in13_V4` is importable (see Waveshare's wiki for the 2.13" V4 hat).
3. Clone this repo and create a virtualenv:
   ```sh
   git clone https://github.com/mechSammich/paper-window.git ~/paper-window
   cd ~/paper-window
   python3 -m venv .venv
   .venv/bin/pip install -e ".[pi]"
   cp config.example.toml config.toml   # then set server url, username, password
   ```
4. Run it: `.venv/bin/python -m paper_window --config config.toml`
5. Optional autostart: copy `deploy/paper-window.service` to `/etc/systemd/system/`, adjust paths, then `sudo systemctl enable --now paper-window`.

Set `username` and `password` to your SilverBullet login credentials (in single-space mode,
these match `SB_USER=username:password`). The client logs in at `/.auth` and keeps the
session cookie in memory, logging in again if the session expires. Alternatively, set
`token` to a SilverBullet API bearer token; it takes precedence over the login credentials.
Leave all three empty for an unauthenticated server.

Use HTTPS on untrusted networks: HTTP sends credentials and page contents without encryption.
HTTPS certificates are verified using the system trust store. Keep `config.toml` private
because it contains credentials or a token.

## simulate without hardware
```sh
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m paper_window --config config.example.toml --simulate
```
Each frame is written to `simulated-display.png`. Type `j`/`k` for next/previous task, Enter to toggle, `n`/`p` for next/previous page, and `q` to quit.

## tests
```sh
.venv/bin/python -m pytest
```

## button pins
Defaults are BCM 5 (next task), 6 (previous task), 13 (toggle), 19 (next page), 26 (previous page), each wired to GND. Change them in the `[buttons]` section if your hat uses different pins.
