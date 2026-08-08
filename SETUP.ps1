param(
    [string]$Distro = 'Ubuntu-22.04',
    [string]$WebotsPath = ''
)

$ErrorActionPreference = 'Stop'
$workspace = $PSScriptRoot
. (Join-Path $workspace 'scripts\windows_helpers.ps1')

Write-Host '[1/4] Checking WSL...' -ForegroundColor Cyan
Assert-WslDistro -Distro $Distro

Write-Host '[2/4] Checking Webots...' -ForegroundColor Cyan
$webots = Find-WebotsExecutable -ExplicitPath $WebotsPath
Write-Host "  $webots"

Write-Host '[3/4] Checking Windows Python...' -ForegroundColor Cyan
$python = Find-PythonExecutable
Write-Host "  $python"

Write-Host '[4/4] Installing ROS 2 dependencies and building the simulator...' -ForegroundColor Cyan
Write-Host '  WSL may ask for your Linux sudo password.'
$linuxRoot = Convert-ToWslPath -Path $workspace
$quotedRoot = Convert-ToBashLiteral -Value $linuxRoot
$command = "cd $quotedRoot && chmod +x scripts/*.sh && ./scripts/setup_wsl.sh"

& wsl.exe -d $Distro -- bash -lc $command
if ($LASTEXITCODE -ne 0) {
    throw "WSL setup failed with exit code $LASTEXITCODE. Read the last error above, then run SETUP.cmd again."
}

Write-Host ''
Write-Host '[OK] Setup complete. Double-click START.cmd to run a match.' -ForegroundColor Green
