#!/usr/bin/env python3
"""Claude Code status line: model, cwd, context bar, official 5h/weekly quota."""
import glob
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CLAUDE_DIR = os.path.expanduser("~/.claude")
CREDS_FILE = os.path.join(CLAUDE_DIR, ".credentials.json")
USAGE_CACHE_FILE = os.path.join(CLAUDE_DIR, ".statusline_usage.json")
USAGE_TTL_SEC = 60  # serve cached usage for this long before kicking a background refresh
USAGE_HARD_TTL_SEC = 600  # after this, drop cache and show "—"
USAGE_ENDPOINT = "https://api.anthropic.com/api/oauth/usage"
USAGE_TIMEOUT_SEC = 2.5  # statusline budget is 300ms — cap the blocking fetch tight

BAR_WIDTH = 15


def normalize(p: str) -> str:
    if os.name == "nt" and len(p) > 2 and p[0] == "/" and p[2] == "/" and p[1].isalpha():
        return p[1].upper() + ":" + p[2:].replace("/", "\\")
    return p


def make_bar(pct: float, width: int = BAR_WIDTH) -> str:
    clamped = max(0.0, min(100.0, pct))
    filled = round(clamped / 100.0 * width)
    empty = width - filled
    return "[" + "█" * filled + "░" * empty + "]"


def read_access_token():
    try:
        with open(CREDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)["claudeAiOauth"]["accessToken"]
    except Exception:
        return None


def fetch_usage_now():
    """Synchronous fetch of the official quota endpoint. Returns dict or None."""
    tok = read_access_token()
    if not tok:
        return None
    req = urllib.request.Request(
        USAGE_ENDPOINT,
        headers={
            "Authorization": f"Bearer {tok}",
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "claude-statusline/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=USAGE_TIMEOUT_SEC) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return None


def write_cache(payload):
    try:
        tmp = USAGE_CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"time": time.time(), "payload": payload}, f)
        os.replace(tmp, USAGE_CACHE_FILE)
    except OSError:
        pass


def read_cache():
    try:
        with open(USAGE_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def spawn_background_refresh():
    """Fork a detached process to refresh the cache without blocking the statusline."""
    try:
        creationflags = 0
        if os.name == "nt":
            creationflags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            [sys.executable, __file__, "--refresh-usage"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=(os.name != "nt"),
            creationflags=creationflags,
        )
    except OSError:
        pass


def get_usage():
    """Return (five_hour_pct, seven_day_pct, fresh: bool). None values when unavailable."""
    cached = read_cache()
    now = time.time()
    if cached:
        age = now - cached.get("time", 0)
        payload = cached.get("payload") or {}
        if age < USAGE_TTL_SEC:
            return _extract(payload) + (True,)
        if age < USAGE_HARD_TTL_SEC:
            spawn_background_refresh()
            return _extract(payload) + (False,)
    # No cache or expired: do one blocking fetch (capped by USAGE_TIMEOUT_SEC).
    payload = fetch_usage_now()
    if payload:
        write_cache(payload)
        return _extract(payload) + (True,)
    return (None, None, False)


def _extract(payload):
    def pct(node):
        if isinstance(node, dict):
            u = node.get("utilization")
            if isinstance(u, (int, float)):
                return float(u)
        return None
    return (pct(payload.get("five_hour")), pct(payload.get("seven_day")))


def current_context_tokens(transcript_path):
    if not transcript_path or not os.path.exists(transcript_path):
        return 0
    last_ctx = 0
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                msg = entry.get("message") or {}
                if not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                if not usage:
                    continue
                last_ctx = (
                    usage.get("input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                )
    except OSError:
        pass
    return last_ctx


def short_cwd(path: str) -> str:
    if not path:
        return "~"
    home = os.path.expanduser("~")
    norm_path = path.replace("\\", "/")
    norm_home = home.replace("\\", "/")
    if norm_path.lower().startswith(norm_home.lower()):
        path = "~" + path[len(home):]
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    if len(parts) <= 2:
        return path.replace("\\", "/")
    return "…/" + "/".join(parts[-2:])


def render(data):
    model = data.get("model") or {}
    model_id = (model.get("id") or "").lower()
    model_name = model.get("display_name") or "Claude"
    transcript_path = normalize(data.get("transcript_path") or "")

    workspace = data.get("workspace") or {}
    cwd_raw = normalize(workspace.get("current_dir") or data.get("cwd") or "")
    cwd_display = short_cwd(cwd_raw)

    is_1m = "1m" in model_id or "opus-4" in model_id or "opus4" in model_id
    context_limit = 1_000_000 if is_1m else 200_000

    ctx_pct_pre = (data.get("context_window") or {}).get("used_percentage")
    last_ctx = current_context_tokens(transcript_path)
    if ctx_pct_pre is not None:
        pct = float(ctx_pct_pre)
    elif context_limit:
        pct = last_ctx / context_limit * 100
    else:
        pct = 0.0

    pct_5h, pct_wk, fresh = get_usage()
    cost_usd = (data.get("cost") or {}).get("total_cost_usd")

    purple = "\033[38;2;187;154;247m"
    dim    = "\033[38;2;86;95;137m"
    cyan   = "\033[38;2;125;207;255m"
    yellow = "\033[38;2;224;175;104m"
    reset  = "\033[0m"

    def color_for(p):
        if p is None:
            return dim
        if p < 50:
            return "\033[38;2;158;206;106m"
        if p < 80:
            return "\033[38;2;224;175;104m"
        return "\033[38;2;247;118;142m"

    def gauge(p):
        if p is None:
            return f"{dim}{make_bar(0)}  —%{reset}"
        return f"{color_for(p)}{make_bar(p)} {p:.0f}%{reset}"

    sep = f" {dim}·{reset} "
    bar = make_bar(pct)

    if cost_usd is None:
        cost_seg = ""
    elif cost_usd >= 1:
        cost_seg = f"{sep}{yellow}${cost_usd:,.2f}{reset}"
    else:
        cost_seg = f"{sep}{yellow}${cost_usd:.3f}{reset}"

    stale = "" if fresh else f"{dim}·{reset}"

    line = (
        f"{purple}● {model_name}{reset}{sep}"
        f"{cyan}{cwd_display}{reset}{sep}"
        f"{color_for(pct)}{bar} {pct:.0f}%{reset}"
        f"{cost_seg}{sep}"
        f"{dim}5h{stale}{reset} {gauge(pct_5h)}{sep}"
        f"{dim}wk{stale}{reset} {gauge(pct_wk)}"
    )
    sys.stdout.write(line)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--refresh-usage":
        payload = fetch_usage_now()
        if payload:
            write_cache(payload)
        return
    try:
        data = json.loads(sys.stdin.read())
    except (ValueError, OSError):
        sys.stdout.write("statusline parse error")
        return
    render(data)


if __name__ == "__main__":
    main()
