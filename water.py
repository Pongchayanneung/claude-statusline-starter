#!/usr/bin/env python3
"""Estimate water consumption from Claude Code JSONL token logs.

Coefficient blended from arxiv 2505.09598 ("How Hungry is AI?", May 2026):
    Claude-3.7 Sonnet on AWS = 8.7 mL per 2k tokens => 4.35 microliters/token.

Cache-read tokens are discounted to 0.1x because cache reads avoid the
attention recompute that dominates per-token energy.

Lifetime totals are computed by scanning every JSONL under
``~/.claude/projects/`` and cached at ``~/.claude/water_total.json`` keyed
by (path, mtime, size). The cache makes the statusline render hot path
near-free even with hundreds of session files.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

MICROLITERS_PER_TOKEN: float = 4.35  # Sonnet 3.7 AWS blended (arxiv 2505.09598)
CACHE_READ_FACTOR: float = 0.1
ETH_CHILD_DAILY_LITERS: float = 5.0  # WHO short-term survival floor, child
BATHTUB_LITERS: float = 150.0

CACHE_PATH: Path = Path.home() / ".claude" / "water_total.json"
JSONL_ROOT: Path = Path.home() / ".claude" / "projects"


def effective_tokens(usage: dict) -> int:
    """Sum tokens with 0.1x discount on cache_read."""
    if not isinstance(usage, dict):
        return 0
    inp = usage.get("input_tokens") or 0
    cc = usage.get("cache_creation_input_tokens") or 0
    cr = usage.get("cache_read_input_tokens") or 0
    out = usage.get("output_tokens") or 0
    return int(inp + cc + cr * CACHE_READ_FACTOR + out)


def tokens_to_ml(tokens: int) -> float:
    return tokens * MICROLITERS_PER_TOKEN / 1000.0


def eth_child_days(ml: float) -> float:
    return ml / (ETH_CHILD_DAILY_LITERS * 1000.0)


def format_water(ml: float) -> str:
    """Auto-scale: <1000 mL -> mL; <150 L -> L; else bathtubs."""
    if ml < 1000:
        return f"{ml:.0f}mL"
    liters = ml / 1000.0
    if liters < BATHTUB_LITERS:
        return f"{liters:.1f}L"
    return f"{liters / BATHTUB_LITERS:.1f}tub"


def _sum_jsonl_tokens(path: Path) -> int:
    total = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"usage"' not in line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                msg = record.get("message") if isinstance(record, dict) else None
                usage = None
                if isinstance(msg, dict):
                    usage = msg.get("usage")
                if usage is None and isinstance(record, dict):
                    usage = record.get("usage")
                if usage:
                    total += effective_tokens(usage)
    except OSError:
        return 0
    return total


def session_tokens(transcript_path: Optional[str]) -> int:
    if not transcript_path:
        return 0
    p = Path(transcript_path)
    if not p.exists():
        return 0
    return _sum_jsonl_tokens(p)


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {"files": {}, "total_tokens": 0}
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {"files": {}, "total_tokens": 0}


def _save_cache(cache: dict) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cache), encoding="utf-8")
        tmp.replace(CACHE_PATH)
    except OSError:
        return


def lifetime_tokens() -> int:
    """Sum tokens across all JSONLs under ~/.claude/projects/, mtime-cached."""
    if not JSONL_ROOT.exists():
        return 0

    cache = _load_cache()
    prior_files = cache.get("files") or {}
    new_files: dict = {}
    total = 0
    dirty = False

    for jsonl in JSONL_ROOT.rglob("*.jsonl"):
        try:
            st = jsonl.stat()
        except OSError:
            continue
        key = str(jsonl)
        prior = prior_files.get(key)
        if (
            isinstance(prior, dict)
            and prior.get("mtime") == st.st_mtime
            and prior.get("size") == st.st_size
            and isinstance(prior.get("tokens"), (int, float))
        ):
            tokens = int(prior["tokens"])
        else:
            tokens = _sum_jsonl_tokens(jsonl)
            dirty = True
        new_files[key] = {"mtime": st.st_mtime, "size": st.st_size, "tokens": tokens}
        total += tokens

    if dirty or set(new_files) != set(prior_files):
        _save_cache({"files": new_files, "total_tokens": total})
    return total


if __name__ == "__main__":
    lt_tokens = lifetime_tokens()
    lt_ml = tokens_to_ml(lt_tokens)
    print(f"lifetime: {lt_tokens:,} tokens = {lt_ml:.1f} mL = {eth_child_days(lt_ml):.2f} ETHc (Ethiopian-child-days)")
