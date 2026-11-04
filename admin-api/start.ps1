$ErrorActionPreference = 'Stop'
$apiRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$existing = Get-NetTCPConnection -LocalPort 8200 -State Listen -ErrorAction SilentlyContinue

if ($existing) {
  $healthText = & curl.exe -s --max-time 2 http://127.0.0.1:8200/health
  if ($LASTEXITCODE -eq 0 -and $healthText -match '"status"\s*:\s*"ok"') {
    Write-Host 'Zhiyu admin API is already running at http://127.0.0.1:8200.' -ForegroundColor Green
    Write-Host $healthText
    exit 0
  }
  throw "Port 8200 is already used by process $($existing[0].OwningProcess). Stop that process, then run this script again."
}

& "$apiRoot\.venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8200 --reload
