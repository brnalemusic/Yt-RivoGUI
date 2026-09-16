# PowerShell script to test Yt-RivoGUI executable build
param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    Write-Error "python executable not found in PATH."
    exit 1
}

$ArgsList = @("devscripts/test_build.py")
if ($Build) {
    $ArgsList += "--build"
}

Write-Host "Running build tests for Yt-RivoGUI..." -ForegroundColor Cyan
& $PythonExe $ArgsList
exit $LASTEXITCODE
