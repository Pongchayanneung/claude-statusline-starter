# claude-statusline-starter

Drop-in status line for [Claude Code](https://claude.com/claude-code). Shows model, working directory, and git branch under the prompt input box.

```
[Opus 4.7] my-project (main) | tokens: 12,345
```

## Quick install

### Option A — let Claude Code wire it up (easiest)

1. Copy `statusline.ps1` (Windows) or `statusline.sh` (macOS/Linux) into `~/.claude/`
2. In Claude Code, run:
   ```
   /statusline
   ```
3. Tell it: *"Use the script at `~/.claude/statusline.ps1`"* (or `.sh`)

Claude Code edits `settings.json` for you.

### Option B — manual

1. Copy the script into `~/.claude/` and (on macOS/Linux) `chmod +x ~/.claude/statusline.sh`
2. Merge `settings.example.json` into `~/.claude/settings.json`
3. Restart Claude Code

## What's in this repo

| File | Purpose |
|------|---------|
| `statusline.ps1` | PowerShell version — Windows |
| `statusline.sh` | Bash version — macOS / Linux / WSL |
| `settings.example.json` | Snippet to merge into `~/.claude/settings.json` |

## How it works

Claude Code pipes JSON to your script on stdin every ≤300 ms:

```json
{
  "model": { "display_name": "Opus 4.7" },
  "workspace": { "current_dir": "/path/to/project" },
  "session_id": "...",
  "transcript_path": "...",
  "output_style": { "name": "default" }
}
```

The script's **first stdout line** becomes the status line. ANSI colors work. Timeout 300 ms — keep it fast.

## Customize

Edit the script. Common additions:

- **Git branch** — already included
- **Token usage** — read `transcript_path`, sum `usage.*` from the JSONL
- **Cost** — same as tokens, multiply by model price
- **Time** — `Get-Date` / `date`

## Requirements

- Claude Code ≥ 1.0.x (statusLine config supported)
- PowerShell 5.1+ (Windows) or bash + `jq` (macOS/Linux)

## License

MIT
