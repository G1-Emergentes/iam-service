$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & '.\.sam-venv\Scripts\python.exe' -m uvicorn sam.mobile_api:app --host 127.0.0.1 --port 8093 --no-access-log
} finally { Pop-Location }
