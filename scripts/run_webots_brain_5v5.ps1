param(
    [string]$Distro = 'Ubuntu-22.04',
    [string]$WebotsPath = ''
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'windows_helpers.ps1')

$world = Join-Path $workspace 'sim_webots\worlds\football_5v5_brain.wbt'
$relay = Join-Path $PSScriptRoot 'webots_relay.ps1'
$ports = @(10081, 10082, 10083)
$webots = Find-WebotsExecutable -ExplicitPath $WebotsPath
$python = Find-PythonExecutable
Assert-WslDistro -Distro $Distro
$env:PATH = (Split-Path -Parent $python) + ';' + $env:PATH

function Stop-SimulatorPortOwners {
    $processIds = @(
        Get-NetUDPEndpoint -ErrorAction SilentlyContinue |
            Where-Object { $_.LocalPort -in $ports } |
            Select-Object -ExpandProperty OwningProcess
        Get-NetTCPConnection -ErrorAction SilentlyContinue |
            Where-Object { $_.LocalPort -in $ports } |
            Select-Object -ExpandProperty OwningProcess
    ) | Where-Object { $_ -and $_ -ne $PID } | Sort-Object -Unique

    foreach ($processId in $processIds) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($null -ne $process) {
            Write-Host "  stopping PID=$processId ($($process.ProcessName))"
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Stop-SimulatorWebots {
    $worldName = Split-Path -Leaf $world
    $instances = Get-CimInstance Win32_Process -Filter "Name = 'webots.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$worldName*" }
    foreach ($instance in $instances) {
        Stop-Process -Id $instance.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Wait-ForTcpListener {
    param([int]$Port, [int]$TimeoutSeconds = 10)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { return $true }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    return $false
}

Write-Host '[0/5] Checking files and programs...' -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $world -PathType Leaf)) { throw "World not found: $world" }
if (-not (Test-Path -LiteralPath $relay -PathType Leaf)) { throw "Relay not found: $relay" }

Write-Host '[1/5] Stopping the previous simulator instance...' -ForegroundColor Cyan
Stop-SimulatorWebots
Stop-SimulatorPortOwners
$linuxRoot = Convert-ToWslPath -Path $workspace
$quotedRoot = Convert-ToBashLiteral -Value $linuxRoot
$cleanup = "cd $quotedRoot && ./scripts/stop_webots_brain_5v5.sh >/dev/null 2>&1 || true"
& wsl.exe -d $Distro -- bash -lc $cleanup
Start-Sleep -Seconds 1
Stop-SimulatorPortOwners

Write-Host '[2/5] Starting the built-in Windows/WSL relay...' -ForegroundColor Cyan
$relayProcess = Start-Process -FilePath 'powershell.exe' `
    -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $relay + '"')) `
    -WorkingDirectory $PSScriptRoot -PassThru
Set-Content -LiteralPath (Join-Path $env:TEMP 'webots_5v5_brain_relay.pid') -Value $relayProcess.Id
if (-not (Wait-ForTcpListener -Port 10083)) {
    $relayProcess.Refresh()
    if ($relayProcess.HasExited) { throw "Relay exited with code $($relayProcess.ExitCode)." }
    throw 'Relay did not listen on TCP 10083 within 10 seconds.'
}

Write-Host '[3/5] Starting both ROS 2 Brains in WSL...' -ForegroundColor Cyan
$wslCommand = "cd $quotedRoot && WEBOTS_GATEWAY_HOST=127.0.0.1 ./scripts/start_webots_brain_5v5.sh"
$wslArgs = "-d $Distro -- bash -lc `"$wslCommand`""
Start-Process -FilePath 'wsl.exe' -ArgumentList $wslArgs -WorkingDirectory $workspace
Start-Sleep -Seconds 8

Write-Host '[4/5] Starting Webots...' -ForegroundColor Cyan
$env:WEBOTS_ROS_HOST = '127.0.0.1'
Start-Process -FilePath $webots -ArgumentList @($world) -WorkingDirectory (Split-Path $webots)

Write-Host '[5/5] Startup requested.' -ForegroundColor Cyan
Write-Host ''
Write-Host '[OK] Webots 5v5 Brain Simulator is starting.' -ForegroundColor Green
Write-Host 'Robots should begin moving after Webots and all ROS 2 nodes are ready.'
