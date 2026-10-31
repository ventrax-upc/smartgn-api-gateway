$ErrorActionPreference='Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
docker run --rm -v "${PWD}:/workspace" -w /workspace node:22-alpine sh -c 'npm ci --ignore-scripts --no-audit --no-fund && npm test'
if($LASTEXITCODE -ne 0){throw 'Gateway verification failed'}
