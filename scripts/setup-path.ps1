# ==============================================================================
# Prime Gate - Windows Environment Variable & Global CLI Setup
# Configures 'prime-gate' to be callable globally from any terminal.
# ==============================================================================

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Prime Gate Global CLI & PATH Automator for Windows    " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Determine Repository Root
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
Write-Host "[1/4] Repository root: $RepoRoot" -ForegroundColor Gray

# 2. Check Python Availability
try {
    $pythonCmd = Get-Command python.exe -ErrorAction Stop
    $pythonPath = $pythonCmd.Source
    Write-Host "[2/4] Found Python at: $pythonPath" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] python.exe was not found in PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ and make sure it is added to your PATH." -ForegroundColor Yellow
    Exit 1
}

# 3. Perform Editable Package Installation
Write-Host "[3/4] Installing Prime Gate in editable mode (pip install -e .)..." -ForegroundColor Cyan
Push-Location $RepoRoot
try {
    & python -m pip install -e . --no-warn-script-location
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

# 4. Locate Python Scripts Directory & Add to User PATH
Write-Host "[4/4] Verifying and updating Windows User PATH..." -ForegroundColor Cyan

# Determine python Scripts directory
$pythonDir = Split-Path $pythonPath -Parent
$pythonScripts = Join-Path $pythonDir "Scripts"

# Also check user site base scripts
$userBaseScripts = python -c "import site, os; print(os.path.join(site.getuserbase(), 'Scripts'))" 2>$null

$targetDirs = @($pythonScripts)
if ($userBaseScripts -and (Test-Path $userBaseScripts) -and ($userBaseScripts -ne $pythonScripts)) {
    $targetDirs += $userBaseScripts
}

$currentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$userPathParts = if ($currentUserPath) { $currentUserPath.Split(';') | Where-Object { $_ -ne "" } } else { @() }

$pathModified = $false
foreach ($dir in $targetDirs) {
    if (Test-Path $dir) {
        $alreadyInPath = $false
        foreach ($p in $userPathParts) {
            if ($p.TrimEnd('\').Equals($dir.TrimEnd('\'), [System.StringComparison]::OrdinalIgnoreCase)) {
                $alreadyInPath = $true
                break
            }
        }
        if (-not $alreadyInPath) {
            Write-Host "      Adding to User PATH: $dir" -ForegroundColor Yellow
            $userPathParts += $dir
            $pathModified = $true
        } else {
            Write-Host "      Already in User PATH: $dir" -ForegroundColor Gray
        }
        # Update current process PATH so immediate verification works
        $env:Path = "$dir;$env:Path"
    }
}

if ($pathModified) {
    $newUserPath = ($userPathParts -join ";")
    [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
    Write-Host "      Successfully updated Windows User PATH environment variable." -ForegroundColor Green
    Write-Host "      (Note: Existing open terminal windows will need to be reopened to pick up the change)." -ForegroundColor Gray
}

# 5. Verification
Write-Host ""
Write-Host "Testing 'prime-gate --version' command..." -ForegroundColor Cyan
try {
    $ver = & prime-gate --version
    Write-Host "[SUCCESS] Prime Gate CLI is active!" -ForegroundColor Green
    Write-Host $ver -ForegroundColor Gray
} catch {
    Write-Host "[NOTICE] Could not execute 'prime-gate' directly in this session." -ForegroundColor Yellow
    Write-Host "Please restart your terminal (PowerShell / Command Prompt) and try again." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "  Setup Complete! You can now run from ANY directory:   " -ForegroundColor Green
Write-Host "    prime-gate daemon start                             " -ForegroundColor White
Write-Host "    prime-gate daemon status                            " -ForegroundColor White
Write-Host "    prime-gate quota                                    " -ForegroundColor White
Write-Host "    prime-gate ui                                       " -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""
