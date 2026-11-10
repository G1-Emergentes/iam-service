$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & "$PSScriptRoot/.venv/Scripts/python.exe" -m uvicorn api:app --host 127.0.0.1 --port 8091 --no-access-log
    if ($LASTEXITCODE -ne 0) { throw 'Avatar worker failed.' }
} finally { Pop-Location }
