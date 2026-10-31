$ErrorActionPreference='Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
node tools/export-openapi.mjs
if($LASTEXITCODE -ne 0){throw 'OpenAPI export failed'}
