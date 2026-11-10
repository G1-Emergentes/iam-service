param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$model = 'facebook/sam-3d-body-vith'
$revision = 'f7f4ba4f67739e297f291639afb7c59041745367'
$destination = Join-Path $PSScriptRoot 'models/sam-3d-body-vith'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Install uv before downloading the model.'
}
$hfArguments = @('tool', 'run', '--from', 'huggingface_hub==2.4.0', 'hf', 'download', $model,
    '--revision', $revision, '--local-dir', $destination, '--max-workers', '2')
if ($CheckOnly) { $hfArguments += '--dry-run' }
& uv @hfArguments
if ($LASTEXITCODE -ne 0) {
    throw 'Download failed. Verify model access and run: uv tool run --from huggingface_hub==2.4.0 hf auth login'
}
if (-not $CheckOnly) {
    $expected = @{'model.ckpt' = 1691205237; 'assets/mhr_model.pt' = 696110248}
    foreach ($file in $expected.Keys) {
        $path = Join-Path $destination $file
        if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne $expected[$file]) {
            throw "Model file missing or incomplete: $file"
        }
    }
    Write-Output "SAM weights ready at $destination (revision $revision). Inference is not enabled by this script."
}
