$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
try {
    $compose = @('compose','--env-file','.local/integrated.env','-f','compose.integration.yml')
    docker @compose run --rm --no-deps verify python tools/integrated/smoke.py
    if ($LASTEXITCODE -ne 0) { throw 'Integrated smoke failed.' }
    $ids = @(docker @compose ps -q)
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect integrated services.' }
    $samples = @(docker stats --no-stream --format '{{json .}}' @ids)
    if ($LASTEXITCODE -ne 0) { throw 'Cannot measure stack memory.' }
    $samples | Set-Content .local/docker-stats.jsonl
    $usage = 0.0
    foreach ($sample in $samples) {
        $used = (($sample | ConvertFrom-Json).MemUsage -split '/')[0].Trim()
        if ($used -notmatch '^(\d+(?:\.\d+)?)(B|KiB|MiB|GiB)$') {
            throw "Cannot interpret Docker memory sample $used"
        }
        $value = [double]::Parse($Matches[1], [Globalization.CultureInfo]::InvariantCulture)
        $scale = @{ B=1; KiB=1KB; MiB=1MB; GiB=1GB }[$Matches[2]]
        $usage += $value * $scale
    }
    Write-Output ('Stack memory: {0:N2} GiB' -f ($usage / 1GB))
    if ($usage -gt (5.5 * 1GB)) { throw 'Integrated stack exceeded the 5.5 GiB budget.' }
    foreach ($id in $ids) {
        $state = docker inspect --format '{{.State.OOMKilled}}' $id
        if ($LASTEXITCODE -ne 0 -or $state -ne 'false') { throw "Invalid container memory state for $id" }
    }
} finally { Pop-Location }
