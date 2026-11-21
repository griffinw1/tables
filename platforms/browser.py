"""A HEADLESS Chrome for the platforms that need a real browser (OpenTable, Tock).

Always headless (`--headless=new`). It never opens a window, never takes focus, and
never touches your everyday Chrome profile: it uses its own profile directory
(default ~/.dallas-res-watch/chrome-profile, override with DRW_PROFILE).

Why not plain Playwright `chromium.launch()`? OpenTable's bot protection (Akamai)
answers 403 to Playwright-launched headless Chrome. Launching the installed Chrome binary
ourselves and attaching over CDP passes once the UA and client hints say "Google
Chrome" rather than "HeadlessChrome". It was verified 2026-11-18 with a fresh,
empty profile.
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_PROFILE = Path(os.environ.get("DRW_PROFILE", Path.home() / ".dallas-res-watch" / "chrome-profile"))


def chrome_binary() -> str | None:
    if os.environ.get("CHROME_PATH"):
        return os.environ["CHROME_PATH"]
    if os.path.exists(MAC_CHROME):
        return MAC_CHROME
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        p = shutil.which(name)
        if p:
            return p
    return None


def chrome_major(binary: str) -> tuple[str, str]:
    try:
        out = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=20).stdout
        m = re.search(r"(\d+)\.(\d+\.\d+\.\d+)", out)
        if m:
            return m.group(1), m.group(0)
    except Exception:
        pass
    return "142", "142.0.0.0"


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Browser:
    """Holds a headless Chrome + Playwright CDP connection; `page()` returns a disguised tab."""

    def __init__(self, pw, ctx, major: str, full: str):
        self.pw, self.ctx, self.major, self.full = pw, ctx, major, full
        plat = "Macintosh; Intel Mac OS X 10_15_7" if os.uname().sysname == "Darwin" else "X11; Linux x86_64"
        self.ua = (f"Mozilla/5.0 ({plat}) AppleWebKit/537.36 (KHTML, like Gecko) "
                   f"Chrome/{major}.0.0.0 Safari/537.36")
        self.platform = "macOS" if os.uname().sysname == "Darwin" else "Linux"

    def page(self):
        pg = self.ctx.new_page()
        s = self.ctx.new_cdp_session(pg)
        s.send("Network.setUserAgentOverride", {
            "userAgent": self.ua, "acceptLanguage": "en-US,en;q=0.9",
            "platform": "MacIntel" if self.platform == "macOS" else "Linux x86_64",
            "userAgentMetadata": {
                "brands": [{"brand": "Google Chrome", "version": self.major},
                           {"brand": "Chromium", "version": self.major},
                           {"brand": "Not=A?Brand", "version": "24"}],
                "fullVersion": self.full, "platform": self.platform, "platformVersion": "15.5.0",
                "architecture": "arm" if os.uname().machine == "arm64" else "x86",
                "model": "", "mobile": False}})
        return pg


@contextmanager
def headless_chrome(profile: Path | None = None):
    from playwright.sync_api import sync_playwright

    binary = chrome_binary()
    with sync_playwright() as pw:
        if binary is None:
            # Last resort: Playwright's bundled headless shell. OpenTable will likely 403 it.
            b = pw.chromium.launch(headless=True)
            ctx = b.new_context()
            try:
                yield Browser(pw, ctx, "142", "142.0.0.0")
            finally:
                b.close()
            return
        major, full = chrome_major(binary)
        if profile is None:
            profile = DEFAULT_PROFILE
        profile.mkdir(parents=True, exist_ok=True)
        port = _free_port()
        ua_os = "Macintosh; Intel Mac OS X 10_15_7" if os.uname().sysname == "Darwin" else "X11; Linux x86_64"
        args = [binary, "--headless=new", f"--remote-debugging-port={port}",
                f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
                "--disable-background-networking", "--mute-audio", "--window-size=1280,1600",
                f"--user-agent=Mozilla/5.0 ({ua_os}) AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{major}.0.0.0 Safari/537.36"]
        if os.environ.get("CI"):
            args += ["--no-sandbox", "--disable-dev-shm-usage"]
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
        try:
            b = None
            for _ in range(40):
                try:
                    b = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                    break
                except Exception:
                    time.sleep(0.25)
            if b is None:
                raise RuntimeError("headless Chrome did not start")
            ctx = b.contexts[0] if b.contexts else b.new_context()
            yield Browser(pw, ctx, major, full)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
