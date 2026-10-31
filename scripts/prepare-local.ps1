$ErrorActionPreference='Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$source='../smartgn-payments-billing/.env'
if(-not (Test-Path $source)){throw 'Prepare the shared environment with ../smartgn-payments-billing/scripts/prepare-local.ps1 first.'}
$shared=@{}
foreach($line in Get-Content $source){if($line -match '^([A-Z_]+)=(.*)$'){$shared[$Matches[1]]=$Matches[2]}}
if(-not $shared['JWT_SECRET']){throw 'The shared IAM JWT key is missing.'}
if(-not (Test-Path .env)){Copy-Item .env.example .env}
$settings=@{}
foreach($line in Get-Content .env){if($line -match '^([A-Z_]+)=(.*)$'){$settings[$Matches[1]]=$Matches[2]}}
if(-not $settings['JWT_SECRET'] -or $settings['JWT_SECRET'].StartsWith('replace-')){$settings['JWT_SECRET']=$shared['JWT_SECRET']}
elseif($settings['JWT_SECRET'] -ne $shared['JWT_SECRET']){throw 'Gateway JWT_SECRET differs from the shared IAM key. Reconcile the local configuration before starting.'}
$settings.GetEnumerator() | Sort-Object Name | ForEach-Object {"$($_.Name)=$($_.Value)"} | Set-Content .env
Write-Output 'Gateway configuration prepared with the existing IAM key; secrets are not printed.'
