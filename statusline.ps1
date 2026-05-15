# Claude Code status line — PowerShell
# Reads JSON from stdin, prints one line to stdout.

$raw = [Console]::In.ReadToEnd()
if (-not $raw) { return }

try {
    $ctx = $raw | ConvertFrom-Json
} catch {
    Write-Host "[statusline parse error]" -NoNewline
    return
}

$model = $ctx.model.display_name
$cwd   = $ctx.workspace.current_dir
$dir   = if ($cwd) { Split-Path $cwd -Leaf } else { "~" }

# Git branch (silent if not a repo)
$branch = ""
if ($cwd -and (Test-Path $cwd)) {
    Push-Location $cwd
    try {
        $b = git rev-parse --abbrev-ref HEAD 2>$null
        if ($LASTEXITCODE -eq 0 -and $b) { $branch = " ($b)" }
    } catch {}
    Pop-Location
}

# ANSI colors
$esc   = [char]27
$cyan  = "$esc[36m"
$green = "$esc[32m"
$gray  = "$esc[90m"
$reset = "$esc[0m"

Write-Host "$cyan[$model]$reset $green$dir$reset$gray$branch$reset" -NoNewline
