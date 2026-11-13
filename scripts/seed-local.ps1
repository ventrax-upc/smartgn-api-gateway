$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
try {
    docker compose --env-file .local/integrated.env -f compose.integration.yml run --rm --no-deps verify python tools/integrated/seed.py
    if ($LASTEXITCODE -ne 0) { throw 'Demo seed failed.' }
} finally { Pop-Location }
