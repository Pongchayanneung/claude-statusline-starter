#!/usr/bin/env python3
"""Claude Code status line: model, cwd, context, cost, official 5h/weekly quota.

Compact single-line layout (~55 chars typical) so it fits inside split-screen
terminals. Reads quota directly from `data.rate_limits` supplied by Claude Code
2.1+, so there is no network call and no cache.
"""
import io
import json
import os
import sys

import water

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def normalize(p: str) -> str:
    if os.name == "nt" and len(p) > 2 and p[0] == "/" and p[2] == "/" and p[1].isalpha():
        return p[1].upper() + ":" + p[2:].replace("/", "\\")
    return p


def short_cwd(path: str) -> str:
    if not path:
        return "~"
    home = os.path.expanduser("~")
    norm_path = path.replace("\\", "/")
    norm_home = home.replace("\\", "/")
    if norm_path.lower().startswith(norm_home.lower()):
        path = "~" + path[len(home):]
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    if not parts:
        return "~"
    # Keep only the last folder name to save horizontal room
    last = parts[-1]
    if last == "~":
        return "~"
    return "~/" + last if path.startswith("~") else last


def pct_value(node):
    if not isinstance(node, dict):
        return None
    for key in ("used_percentage", "utilization"):
        v = node.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def render(data):
    model = data.get("model") or {}
    model_name = model.get("display_name") or "Claude"

    workspace = data.get("workspace") or {}
    cwd_raw = normalize(workspace.get("current_dir") or data.get("cwd") or "")
    cwd_display = short_cwd(cwd_raw)

    ctx_node = data.get("context_window") or {}
    ctx_pct = ctx_node.get("used_percentage")
    if not isinstance(ctx_pct, (int, float)):
        ctx_pct = 0.0
    ctx_pct = float(ctx_pct)

    rl = data.get("rate_limits") or {}
    pct_5h = pct_value(rl.get("five_hour"))
    pct_wk = pct_value(rl.get("seven_day"))

    cost_usd = (data.get("cost") or {}).get("total_cost_usd")

    purple = "\033[38;2;187;154;247m"
    dim    = "\033[38;2;86;95;137m"
    cyan   = "\033[38;2;125;207;255m"
    yellow = "\033[38;2;224;175;104m"
    bg_white = "\033[48;2;255;255;255m"
    bg_off   = "\033[49m"
    reset  = "\033[0m"

    def color_for(p):
        if p is None:
            return dim
        if p < 50:
            return "\033[38;2;158;206;106m"
        if p < 80:
            return "\033[38;2;224;175;104m"
        return "\033[38;2;247;118;142m"

    def pct_chip(label, p):
        if p is None:
            return f"{dim}{label} —%{reset}"
        return f"{dim}{label}{reset}{color_for(p)}{p:.0f}%{reset}"

    sep = "  "  # double-space group separator — readable, narrow-terminal-friendly

    if cost_usd is None:
        cost_seg = ""
    elif cost_usd >= 1:
        cost_seg = f" {yellow}${cost_usd:,.2f}{reset}"
    else:
        cost_seg = f" {yellow}${cost_usd:.3f}{reset}"

    ctx_seg = (
        f"{color_for(ctx_pct)}{ctx_pct:.0f}%{reset}"
        if isinstance(ctx_pct, (int, float))
        else f"{dim}—%{reset}"
    )

    blue = "\033[38;2;125;207;255m"
    try:
        transcript_path = data.get("transcript_path")
        session_ml = water.tokens_to_ml(water.session_tokens(transcript_path))
        lifetime_ml = water.tokens_to_ml(water.lifetime_tokens())
        eth_c = water.eth_child_days(lifetime_ml)
        water_seg = (
            f"{blue}💧{water.format_water(session_ml)}{reset}"
            f"{dim}·{reset}"
            f"{blue}{eth_c:.1f}{bg_white}🧒🏿{bg_off}{reset}"
        )
    except Exception:
        water_seg = ""

    line = (
        f"{purple}● {model_name}{reset}{sep}"
        f"{cyan}{cwd_display}{reset}{sep}"
        f"{ctx_seg}{cost_seg}{sep}"
        f"{pct_chip('5h ', pct_5h)}{sep}"
        f"{pct_chip('wk ', pct_wk)}"
    )
    if water_seg:
        line += f"{sep}{water_seg}"
    sys.stdout.write(line)


def main():
    try:
        data = json.loads(sys.stdin.read())
    except ValueError:
        sys.stdout.write("statusline parse error")
        return
    render(data)


if __name__ == "__main__":
    main()
