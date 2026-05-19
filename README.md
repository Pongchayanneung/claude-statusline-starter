# claude-statusline-starter

Drop-in status line for [Claude Code](https://claude.com/claude-code). Shows model, working directory, git branch, **session cost ($)**, context window %, and the **official 5h / 7-day quota** (same numbers `/usage` displays).

```
● Opus 4.7  ~/my-project  14% $3.46  5h 29%  wk 8%
```

Compact single-line layout (~55 chars) so it doesn't overflow when you run Claude Code in split-screen terminals.

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

- **Context %** — current usage of the model's context window. Turns amber at 50%, red at 80%.
- **Session cost** — `$X.XX` (≥$1) or `$0.XXX` (<$1), pulled straight from Claude Code's `cost.total_cost_usd` field. Resets per session.
- **5h / weekly meters** *(Python only)* — read directly from `data.rate_limits.{five_hour,seven_day}.used_percentage`, which Claude Code 2.1+ embeds in the JSON it pipes to the status line. Same numbers `/usage` shows, no network call, no cache.

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

- **Layout / separators** — edit the `line = …` block in `render()`. The double-space `sep` keeps the line readable without dot decorations and frees up horizontal room.
- **Colors** — RGB triples near the top of `render()`
- **Add lines added/removed** — read `cost.total_lines_added` / `cost.total_lines_removed`
- **Wider cwd** — `short_cwd()` only keeps the leaf folder by default; loosen it if your terminal is wide

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
