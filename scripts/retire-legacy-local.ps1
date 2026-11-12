$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $repo
try {
    $projects = @('smartgn-billing','smartgn-billing-integration','smartgn-local','smartgn-management-service',
        'smartgn-gateway','smartgn-support','smartgn-installation','smartgn-iam',
        'smartgn-alerting','smartgn-telemetry','smartgn-monitoring','smartgn-config','smartgn-admin','smartgn-message-broker')
    $backup = New-Item -ItemType Directory -Force ".local/retired-$(Get-Date -Format 'yyyyMMdd-HHmmss-fff')"
    foreach ($project in $projects) {
        $label = "label=com.docker.compose.project=$project"
        $running = @(docker ps -q --filter $label)
        if ($LASTEXITCODE -ne 0) { throw "Cannot inspect $project" }
        if ($running.Count) {
            docker stop @running
            if ($LASTEXITCODE -ne 0) { throw "Cannot stop $project" }
        }
        $containers = @(docker ps -aq --filter $label)
        if ($LASTEXITCODE -ne 0) { throw "Cannot list containers for $project" }
        $volumes = @(docker volume ls -q --filter $label)
        if ($LASTEXITCODE -ne 0) { throw "Cannot list volumes for $project" }
        foreach ($volume in $volumes) {
            if ($volume -notmatch '^[-a-zA-Z0-9_]+$') { throw "Unexpected volume name $volume" }
            docker run --rm --mount "type=volume,source=$volume,target=/source,readonly" --mount "type=bind,source=$($backup.FullName),target=/backup" postgres:18 sh -ec 'tar -C /source -czf "/backup/$1.tar.gz" . && tar -tzf "/backup/$1.tar.gz" >/dev/null' backup $volume
            if ($LASTEXITCODE -ne 0) { throw "Backup verification failed for $volume" }
            Get-FileHash -Algorithm SHA256 (Join-Path $backup.FullName "$volume.tar.gz") |
                ForEach-Object { "$($_.Hash)  $volume.tar.gz" } | Add-Content (Join-Path $backup.FullName 'SHA256SUMS')
        }
        if ($containers.Count) {
            docker rm @containers
            if ($LASTEXITCODE -ne 0) { throw "Cannot remove containers for $project" }
        }
        if ($volumes.Count) {
            docker volume rm @volumes
            if ($LASTEXITCODE -ne 0) { throw "Cannot remove backed-up volumes for $project" }
        }
        $networks = @(docker network ls -q --filter $label)
        if ($LASTEXITCODE -ne 0) { throw "Cannot list networks for $project" }
        if ($networks.Count) {
            docker network rm @networks
            if ($LASTEXITCODE -ne 0) { throw "Cannot remove networks for $project" }
        }
    }
    Write-Output "Verified volume archives: $($backup.FullName)"
} finally { Pop-Location }
