param([switch]$Integrated,[switch]$SkipBuild)
$ErrorActionPreference='Stop'
$repoRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
if($Integrated){
 & ../smartgn-payments-billing/scripts/prepare-local.ps1
 & ./scripts/prepare-local.ps1
 $arguments=@('compose','--env-file','../smartgn-payments-billing/.env','-f','compose.integration.yml','up','-d','--wait')
}else{
 & ./scripts/prepare-local.ps1
 $arguments=@('compose','--env-file','.env','-f','compose.yml','up','-d','--wait')
}
if(-not $SkipBuild){$arguments+='--build'}
Set-Location -LiteralPath $repoRoot
& docker @arguments
if($LASTEXITCODE -ne 0){throw 'Local startup failed'}
