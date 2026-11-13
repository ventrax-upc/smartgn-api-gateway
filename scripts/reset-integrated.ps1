$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
try {
    docker compose --env-file .local/integrated.env -f compose.integration.yml down --volumes --remove-orphans
    if ($LASTEXITCODE -ne 0) { throw 'Could not reset the local project.' }
    Remove-Item -LiteralPath .local/seed-state.json -ErrorAction SilentlyContinue
    & ./scripts/start-integrated.ps1 -SkipBuild
} finally { Pop-Location }
