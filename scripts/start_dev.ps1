# scripts/start_dev.ps1 — Windows PowerShell equivalent of start_dev.sh
# Usage: powershell -ExecutionPolicy Bypass -File scripts\start_dev.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $ProjectRoot) { $ProjectRoot = (Get-Location).Path -replace '\\scripts$','' }

Write-Host "=== Autonomous AI Scientist — Dev Server ===" -ForegroundColor Cyan

# Determine Python
$PythonPaths = @(
    "$ProjectRoot\.venv\Scripts\python.exe",
    "$ProjectRoot\.venv\bin\python"
)
$Python = "python"
foreach ($p in $PythonPaths) {
    if (Test-Path $p) { $Python = $p; break }
}

Write-Host "[1/2] Starting FastAPI backend on http://localhost:8000" -ForegroundColor Green
$backendJob = Start-Job -ScriptBlock {
    param($py, $root)
    Set-Location "$root\backend"
    & $py -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
} -ArgumentList $Python, $ProjectRoot

Write-Host "[2/2] Serving standalone UI on http://localhost:8080" -ForegroundColor Green
$uiJob = Start-Job -ScriptBlock {
    param($py, $root)
    Set-Location "$root\ui"
    & $py -m http.server 8080
} -ArgumentList $Python, $ProjectRoot

Write-Host ""
Write-Host "  Backend API:   http://localhost:8000" -ForegroundColor Yellow
Write-Host "  Standalone UI: http://localhost:8080" -ForegroundColor Yellow
Write-Host "  API docs:      http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop. Jobs: backend=$($backendJob.Id), ui=$($uiJob.Id)"

try {
    while ($true) {
        Start-Sleep -Seconds 2
        # Stream backend logs
        Receive-Job $backendJob -ErrorAction SilentlyContinue
        Receive-Job $uiJob -ErrorAction SilentlyContinue
    }
} finally {
    Stop-Job $backendJob, $uiJob -ErrorAction SilentlyContinue
    Remove-Job $backendJob, $uiJob -Force -ErrorAction SilentlyContinue
    Write-Host "Servers stopped." -ForegroundColor Red
}
