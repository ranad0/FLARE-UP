param([int]$Port = 8010)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
  if (-not (Test-Path '.venv/Scripts/python.exe')) { throw 'First follow the Python setup commands in README.md.' }
  & ./.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port $Port
} finally { Pop-Location }
