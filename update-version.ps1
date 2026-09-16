# PowerShell helper to update Yt-RivoGUI version (W.X.Y.Z)
param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    Write-Error "python executable not found in PATH."
    exit 1
}

Write-Host "Updating version to $Version..." -ForegroundColor Cyan
& $PythonExe devscripts/update-version.py $Version
exit $LASTEXITCODE
