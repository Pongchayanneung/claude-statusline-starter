# claude-statusline-starter

Drop-in status line for [Claude Code](https://claude.com/claude-code). Shows model, working directory, git branch, **session cost ($)**, context window %, and the **official 5h / 7-day quota** (same numbers `/usage` displays).

```
● Opus 4.7 · my-project · [██░░░░░░░░░░░░░] 14% · $3.46 · 5h [████░░░░░░░░░░░] 29% · wk [█░░░░░░░░░░░░░░] 8%
```

## Pick one

| Script | What it shows | Needs |
|--------|---------------|-------|
| `statusline.py` *(recommended)* | model, cwd, **context bar %**, **session $ cost**, **official 5h quota**, **official weekly quota** | Python 3.8+ |
| `statusline.ps1` | model, cwd, git branch, **session $ cost** | PowerShell 5.1+ (Windows) |
| `statusline.sh` | model, cwd, git branch, **session $ cost** | bash + `jq` (macOS / Linux / WSL) |

The Python version is the richest — context window bar plus the real `/usage` quota meters with colored gauges (green / amber / red). PS / bash are lighter fallbacks.

## Install

1. Copy your chosen script into `~/.claude/` (Windows: `%USERPROFILE%\.claude\`)
2. On macOS/Linux: `chmod +x ~/.claude/statusline.sh`
3. Merge the matching block from `settings.example.json` into `~/.claude/settings.json`
4. Restart Claude Code

Or let Claude wire it up for you — run `/statusline` inside Claude Code and tell it the script path.

## What you'll see

- **Context bar** — fills as the current session approaches the model's context window (200k, or 1M for `*-1m` / Opus 4 variants). Turns amber at 50%, red at 80%.
- **Session cost** — `$X.XX` (≥$1) or `$0.XXX` (<$1), pulled straight from Claude Code's `cost.total_cost_usd` field. Resets per session.
- **5h / weekly meters** *(Python only)* — fetched live from Anthropic's `/api/oauth/usage` endpoint (the same source `/usage` reads). Matches what the in-app `/usage` modal shows. Cached 60s; refreshed in the background so the statusline never blocks.

## How it works

Claude Code pipes JSON to your script on stdin every ≤300 ms:

```json
{
  "model": { "id": "claude-opus-4-7", "display_name": "Opus 4.7" },
  "workspace": { "current_dir": "/path/to/project" },
  "session_id": "...",
  "transcript_path": "/path/to/transcript.jsonl",
  "cost": {
    "total_cost_usd": 0.1234,
    "total_duration_ms": 12345,
    "total_api_duration_ms": 5678,
    "total_lines_added": 50,
    "total_lines_removed": 10
  }
}
```

The script's **first stdout line** becomes the status line. ANSI colors work. Timeout is 300 ms — keep it fast.

## Customize

- **Cache freshness** — `USAGE_TTL_SEC` (default 60s soft, 600s hard before showing `—%`)
- **Network timeout** — `USAGE_TIMEOUT_SEC` (default 2.5s — keeps the blocking fetch under the 300ms statusline budget on cache hits, only matters on first run)
- **Context bar width** — `BAR_WIDTH` constant
- **Colors** — RGB triples near the bottom of `render()`
- **Add lines added/removed** — read `cost.total_lines_added` / `cost.total_lines_removed`

## Files

| File | Purpose |
|------|---------|
| `statusline.py` | Full-featured Python version |
| `statusline.ps1` | PowerShell version (Windows) |
| `statusline.sh` | Bash version (macOS / Linux) |
| `settings.example.json` | Snippets to merge into `~/.claude/settings.json` |

## Requirements

- Claude Code ≥ 1.0.x (statusLine config + `cost` field supported)

## License

MIT
