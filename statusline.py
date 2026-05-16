#!/usr/bin/env python3
"""Claude Code status line: model, cwd, visual context bar, 5h/weekly rolling tokens."""
import glob
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
CACHE_FILE = os.path.expanduser("~/.claude/.statusline_cache.json")
CACHE_TTL_SEC = 5  # rolling-window scan is cached for this many seconds

# Rate-limit ceilings for percent calculation.
# Defaults are rough Claude Max 5x estimates (Anthropic doesn't publish exact
# token caps). Adjust these to match your plan if you want accurate %s:
#   Pro       :  5h ~25M    week ~250M
#   Max 5x    :  5h ~220M   week ~1.4B
#   Max 20x   :  5h ~900M   week ~5B
LIMIT_5H_TOKENS = 220_000_000
LIMIT_WEEKLY_TOKENS = 1_400_000_000

# Context window bar width in characters (filled + empty = BAR_WIDTH)
BAR_WIDTH = 15


def normalize(p: str) -> str:
    if os.name == "nt" and len(p) > 2 and p[0] == "/" and p[2] == "/" and p[1].isalpha():
        return p[1].upper() + ":" + p[2:].replace("/", "\\")
    return p


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)


def parse_ts(s: str):
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def make_bar(pct: float, width: int = BAR_WIDTH) -> str:
    """Return a block-character progress bar string like [████████░░░░░░░]."""
    clamped = max(0.0, min(100.0, pct))
    filled = round(clamped / 100.0 * width)
    empty = width - filled
    return "[" + "█" * filled + "░" * empty + "]"


def scan_rolling_tokens(now_utc):
    """Return (tokens_5h, tokens_7d) summed across every transcript."""
    cutoff_5h = now_utc - timedelta(hours=5)
    cutoff_7d = now_utc - timedelta(days=7)
    cutoff_7d_ts = cutoff_7d.timestamp()

    tok_5h = 0
    tok_7d = 0
    if not os.path.isdir(PROJECTS_DIR):
        return tok_5h, tok_7d

    for fp in glob.glob(os.path.join(PROJECTS_DIR, "*", "*.jsonl")):
        try:
            if os.path.getmtime(fp) < cutoff_7d_ts:
                continue
        except OSError:
            continue
        try:
            with open(fp, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue
                    ts = parse_ts(entry.get("timestamp"))
                    if ts is None:
                        continue
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts < cutoff_7d:
                        continue
                    msg = entry.get("message") or {}
                    usage = msg.get("usage") if isinstance(msg, dict) else None
                    if not usage:
                        continue
                    n = (
                        usage.get("input_tokens", 0)
                        + usage.get("output_tokens", 0)
                        + usage.get("cache_creation_input_tokens", 0)
                        + usage.get("cache_read_input_tokens", 0)
                    )
                    tok_7d += n
                    if ts >= cutoff_5h:
                        tok_5h += n
        except Exception:
            continue
    return tok_5h, tok_7d


def cached_rolling_tokens():
    now = datetime.now(timezone.utc)
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cached = json.load(f)
        if time.time() - cached.get("time", 0) < CACHE_TTL_SEC:
            return int(cached["tok_5h"]), int(cached["tok_7d"])
    except Exception:
        pass
    tok_5h, tok_7d = scan_rolling_tokens(now)
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"time": time.time(), "tok_5h": tok_5h, "tok_7d": tok_7d}, f)
    except Exception:
        pass
    return tok_5h, tok_7d


def current_context_tokens(transcript_path):
    """Read the transcript JSONL and return tokens from the most recent assistant usage entry."""
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
                except Exception:
                    continue
                msg = entry.get("message") or {}
                if not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                if not usage:
                    continue
                # Sum input-side tokens: what is actually in the context window
                last_ctx = (
                    usage.get("input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                )
    except Exception:
        pass
    return last_ctx


def short_cwd(path: str) -> str:
    """Shorten a path to its last two components, replacing home with ~."""
    if not path:
        return "~"
    home = os.path.expanduser("~")
    # Normalise separators for comparison on Windows
    norm_path = path.replace("\\", "/")
    norm_home = home.replace("\\", "/")
    if norm_path.lower().startswith(norm_home.lower()):
        path = "~" + path[len(home):]
    parts = path.replace("\\", "/").split("/")
    # Keep at most the last 2 meaningful parts
    parts = [p for p in parts if p]
    if len(parts) <= 2:
        return path.replace("\\", "/")
    return "…/" + "/".join(parts[-2:])


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        sys.stdout.write("statusline parse error")
        return

    model = data.get("model") or {}
    model_id = (model.get("id") or "").lower()
    model_name = model.get("display_name") or "Claude"
    transcript_path = normalize(data.get("transcript_path") or "")

    # Working directory — prefer workspace.current_dir, fall back to cwd
    workspace = data.get("workspace") or {}
    cwd_raw = workspace.get("current_dir") or data.get("cwd") or ""
    cwd_raw = normalize(cwd_raw)
    cwd_display = short_cwd(cwd_raw)

    # Context window limit: 1 M for opus-4 / any "1m" model, else 200 k
    is_1m = "1m" in model_id or "opus-4" in model_id or "opus4" in model_id
    context_limit = 1_000_000 if is_1m else 200_000

    # First try the pre-calculated field supplied by Claude Code itself
    ctx_pct_pre = data.get("context_window", {}).get("used_percentage")

    last_ctx = current_context_tokens(transcript_path)
    if ctx_pct_pre is not None:
        pct = float(ctx_pct_pre)
    elif context_limit:
        pct = last_ctx / context_limit * 100
    else:
        pct = 0.0

    tok_5h, tok_7d = cached_rolling_tokens()
    pct_5h = (tok_5h / LIMIT_5H_TOKENS * 100) if LIMIT_5H_TOKENS else 0.0
    pct_7d = (tok_7d / LIMIT_WEEKLY_TOKENS * 100) if LIMIT_WEEKLY_TOKENS else 0.0

    cost_usd = (data.get("cost") or {}).get("total_cost_usd")

    # ── ANSI colours ──────────────────────────────────────────────────────────
    purple = "\033[38;2;187;154;247m"
    dim    = "\033[38;2;86;95;137m"
    cyan   = "\033[38;2;125;207;255m"
    reset  = "\033[0m"

    def color_for(p: float) -> str:
        if p < 50:
            return "\033[38;2;158;206;106m"   # green
        if p < 80:
            return "\033[38;2;224;175;104m"   # amber
        return "\033[38;2;247;118;142m"       # red

    ctx_color = color_for(pct)
    c5h = color_for(pct_5h)
    cwk = color_for(pct_7d)
    sep = f" {dim}·{reset} "

    bar = make_bar(pct)
    bar_5h = make_bar(pct_5h)
    bar_wk = make_bar(pct_7d)

    yellow = "\033[38;2;224;175;104m"
    if cost_usd is None:
        cost_seg = ""
    elif cost_usd >= 1:
        cost_seg = f"{sep}{yellow}${cost_usd:,.2f}{reset}"
    else:
        cost_seg = f"{sep}{yellow}${cost_usd:.3f}{reset}"

    line = (
        f"{purple}● {model_name}{reset}{sep}"
        f"{cyan}{cwd_display}{reset}{sep}"
        f"{ctx_color}{bar} {pct:.0f}%{reset}"
        f"{cost_seg}{sep}"
        f"{dim}5h{reset} {c5h}{bar_5h} {pct_5h:.0f}%{reset}{sep}"
        f"{dim}wk{reset} {cwk}{bar_wk} {pct_7d:.0f}%{reset}"
    )
    sys.stdout.write(line)


if __name__ == "__main__":
    main()
