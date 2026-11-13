param([switch]$SkipBuild,[switch]$InfrastructureOnly)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $repo
try {
    New-Item -ItemType Directory -Force .local | Out-Null
    $settings = @{}
    if (Test-Path .local/integrated.env) {
        foreach ($line in Get-Content .local/integrated.env) {
            if ($line -match '^([A-Z_]+)=(.*)$') { $settings[$Matches[1]] = $Matches[2] }
        }
    }
    $template = Get-Content compose.integration.yml -Raw
    $required = [regex]::Matches($template, '\$\{([A-Z_]+):\?') |
        ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
    foreach ($key in $required) {
        if ($settings[$key]) { continue }
        $bytes = [Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
        $settings[$key] = if ($key -in 'DELIVERY_ENCRYPTION_KEY','CARD_ENCRYPTION_KEY','DEVICE_CREDENTIAL_KEY') {
            [Convert]::ToBase64String($bytes)
        } else {
            [Convert]::ToHexString($bytes)
        }
    }
    $settings.GetEnumerator() | Sort-Object Name |
        ForEach-Object { "$($_.Name)=$($_.Value)" } | Set-Content -Encoding ascii .local/integrated.env
    "$($settings.DEVICE_BROKER_API_KEY):$($settings.DEVICE_BROKER_API_SECRET)" |
        Set-Content -Encoding ascii .local/bootstrap-api-keys
    if (-not (Test-Path .local/tax.p12)) {
        $env:TAX_KEY_PASSWORD = $settings.TAX_KEY_PASSWORD
        try {
            $keytool = Get-Command keytool -ErrorAction SilentlyContinue
            $keyArgs = @('-genkeypair','-alias','smartgn-local','-keyalg','RSA','-keysize','2048','-validity','365',
                '-dname','CN=SmartGN LOCAL TEST, O=SmartGN DEMO, C=PE','-storetype','PKCS12',
                '-keystore','tax.p12','-storepass:env','TAX_KEY_PASSWORD','-keypass:env','TAX_KEY_PASSWORD')
            if ($keytool) {
                Push-Location .local
                try { & $keytool.Source @keyArgs } finally { Pop-Location }
            } else {
                & docker run --rm -e TAX_KEY_PASSWORD -v "${repo}/.local:/keys" -w /keys eclipse-temurin:25-jdk keytool @keyArgs
            }
            if ($LASTEXITCODE -ne 0) { throw 'Could not generate the local signing certificate.' }
        } finally { Remove-Item Env:TAX_KEY_PASSWORD -ErrorAction SilentlyContinue }
    }
    $compose = @('compose','--parallel','1','--env-file','.local/integrated.env','-f','compose.integration.yml')
    & docker @compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Invalid integrated Compose configuration.' }
    if ($InfrastructureOnly) {
        & docker @compose up -d --wait --wait-timeout 300 postgres redis influxdb emqx delivery
        if ($LASTEXITCODE -ne 0) { throw 'Integrated infrastructure startup failed.' }
        & docker @compose up --no-deps --exit-code-from emqx-init emqx-init
        if ($LASTEXITCODE -ne 0) { throw 'EMQX initialization failed.' }
        return
    }
    if (-not $SkipBuild) {
        $services = @('config','admin','iam','installation','support','billing','alerting',
            'message-broker','telemetry','monitoring','api-gateway')
        foreach ($service in $services) {
            & docker @compose build $service
            if ($LASTEXITCODE -ne 0) { throw "Docker build failed for $service." }
        }
    }
    & docker @compose up -d --wait --wait-timeout 300 admin api-gateway message-broker telemetry delivery
    if ($LASTEXITCODE -ne 0) { throw 'Integrated startup failed. Inspect Compose ps and logs.' }
} finally {
    Pop-Location
}



