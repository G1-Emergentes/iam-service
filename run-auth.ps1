$ErrorActionPreference = 'Stop'
$config = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path -LiteralPath $config)) {
    throw 'Create .env from .env.example and configure Supabase first.'
}
foreach ($line in Get-Content -LiteralPath $config) {
    if ($line -match '^(SUPABASE_URL|SUPABASE_PUBLISHABLE_KEY)=(.+)$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim(), 'Process')
    }
}
$executable = Join-Path $PSScriptRoot 'out\build\x64-debug-vcpkg\iam-service.exe'
if (-not (Test-Path -LiteralPath $executable)) {
    throw 'Build x64 Debug first. See AUTH.md.'
}
& $executable
exit $LASTEXITCODE
