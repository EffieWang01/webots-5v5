param(
    [string]$Distro = 'Ubuntu-22.04',
    [string]$WebotsPath = '',
    [switch]$SkipSetup
)

$ErrorActionPreference = 'Stop'
$workspace = $PSScriptRoot
. (Join-Path $workspace 'scripts\windows_helpers.ps1')

Assert-WslDistro -Distro $Distro
$linuxRoot = Convert-ToWslPath -Path $workspace
$quotedSetup = Convert-ToBashLiteral -Value "$linuxRoot/install/setup.bash"
& wsl.exe -d $Distro -- bash -lc "test -f $quotedSetup"
$isBuilt = ($LASTEXITCODE -eq 0)

if (-not $isBuilt) {
    if ($SkipSetup) {
        throw 'The simulator is not built. Run SETUP.cmd first.'
    }
    Write-Host '[INFO] First run detected; starting automatic setup.' -ForegroundColor Yellow
    & (Join-Path $workspace 'SETUP.ps1') -Distro $Distro -WebotsPath $WebotsPath
}

& (Join-Path $workspace 'scripts\run_webots_brain_5v5.ps1') `
    -Distro $Distro `
    -WebotsPath $WebotsPath
