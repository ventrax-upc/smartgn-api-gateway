param([string]$SessionBase = "http://api-gateway:8000")
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$compose = @('compose', '--env-file', '.local/integrated.env', '-f', 'compose.integration.yml')
$batch = [Guid]::NewGuid().ToString('N')
function Invoke-Compose {
    & docker @compose @args
    if ($LASTEXITCODE -ne 0) { throw "Compose command failed ($($args[0]))" }
}
function Wait-Count([string]$stage, [int]$expected) {
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        $count = Invoke-Compose exec -T telemetry-postgres psql -U postgres -d smartgn_telemetry -Atc "
          SELECT count(*) FROM telemetry_processing WHERE event_id LIKE '${batch}-%' AND stage = '$stage';"
        if ([int]$count -eq $expected) {
            Write-Output "PASS $count readings in $stage"
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "Timed out waiting for $expected readings in $stage (observed $count)"
}
$faultStarted = $false
try {
    Write-Output "Telemetry recovery batch $batch"
    Invoke-Compose run --rm --no-deps verify python tools/integrated/telemetry_recovery.py prepare $batch --session-base $SessionBase
    Invoke-Compose run --rm --no-deps verify python tools/integrated/telemetry_recovery.py spool $batch
    $faultStarted = $true
    Invoke-Compose stop influxdb alerting
    Invoke-Compose run --rm --no-deps verify python tools/integrated/telemetry_recovery.py send $batch
    Wait-Count 'influx' 360
    Invoke-Compose restart telemetry
    Wait-Count 'influx' 360

    Invoke-Compose start influxdb
    Wait-Count 'alerting' 360
    Invoke-Compose start alerting
    Wait-Count 'done' 360

    Invoke-Compose run --rm --no-deps verify python tools/integrated/telemetry_recovery.py repeat $batch
    Wait-Count 'done' 360
    $pointSlots = Invoke-Compose exec -T telemetry-postgres psql -U postgres -d smartgn_telemetry -Atc "
      SELECT count(DISTINCT point_slot) FROM telemetry_processing WHERE event_id IN ('$batch-0', '$batch-1');"
    if ([int]$pointSlots -ne 2) { throw 'Equal timestamps must have distinct Influx point slots' }
    Write-Output 'PASS independent identities for two same-timestamp readings'

    $receipts = Invoke-Compose exec -T postgres psql -U postgres -d smartgn_alerting_db -Atc "
      SELECT count(*) FROM alerting.telemetry_receipt WHERE event_id LIKE '${batch}-%';"
    if ([int]$receipts -ne 360) { throw "Expected 360 unique Alerting receipts, observed $receipts" }
    $query = @"
from(bucket: "telemetry") |> range(start: -3h)
  |> filter(fn: (r) => r._measurement == "telemetry" and r._field == "eventId")
  |> filter(fn: (r) => r._value =~ /^${batch}-/)
  |> group() |> count()
"@
    $points = Invoke-Compose exec -T influxdb sh -c 'influx query --raw --org smartgn --token "$DOCKER_INFLUXDB_INIT_ADMIN_TOKEN" "$1"' sh $query
    $count = (($points | Where-Object { $_ -like ',,*' } | Select-Object -Last 1) -split ',')[-1]
    if ([int]$count -ne 360) { throw "Expected 360 Influx points, observed $count" }
    Write-Output 'PASS 360 Influx points and 360 unique Alerting receipts'
} finally {
    try {
        if ($faultStarted) {
            Invoke-Compose up -d --no-deps --no-recreate --wait --wait-timeout 300 influxdb alerting telemetry
        }
    } finally { Pop-Location }
}
