param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('red', 'blue')]
    [string]$Team,

    [Parameter(Mandatory = $true)]
    [string]$Source,

    [string]$Name = '',
    [string]$Distro = 'Ubuntu-22.04'
)

$ErrorActionPreference = 'Stop'
$workspace = $PSScriptRoot
. (Join-Path $workspace 'scripts\windows_helpers.ps1')

Assert-WslDistro -Distro $Distro
$resolvedSource = (Resolve-Path -LiteralPath $Source).Path
if ([string]::IsNullOrWhiteSpace($Name)) {
    $item = Get-Item -LiteralPath $resolvedSource
    $baseName = if ($item.PSIsContainer) { $item.Name } else { [IO.Path]::GetFileNameWithoutExtension($item.Name) }
    $Name = $baseName + '_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
}
$Name = ($Name -replace '[^A-Za-z0-9._-]', '_').Trim([char[]]'.-_')
if ([string]::IsNullOrWhiteSpace($Name)) {
    $Name = "${Team}_brain"
}
if ($Name.Length -gt 64) {
    $Name = $Name.Substring(0, 64)
}

$linuxRoot = Convert-ToWslPath -Path $workspace
$linuxSource = Convert-ToWslPath -Path $resolvedSource
$quotedRoot = Convert-ToBashLiteral -Value $linuxRoot
$quotedSource = Convert-ToBashLiteral -Value $linuxSource
$quotedName = Convert-ToBashLiteral -Value $Name

Write-Host "[1/2] Stopping the running simulator before replacing the $Team Brain..." -ForegroundColor Cyan
$stopCommand = "cd $quotedRoot && ./scripts/stop_webots_brain_5v5.sh >/dev/null 2>&1 || true"
& wsl.exe -d $Distro -- bash -lc $stopCommand

Write-Host "[2/2] Validating, backing up, installing, and building '$Name'..." -ForegroundColor Cyan
$importCommand = "cd $quotedRoot && source /opt/ros/humble/setup.bash && python3 scripts/import_brain.py --team $Team --source $quotedSource --name $quotedName"
& wsl.exe -d $Distro -- bash -lc $importCommand
if ($LASTEXITCODE -ne 0) {
    throw 'Brain replacement failed. The importer kept or restored the previous working Brain; see brain_import_reports.'
}

Write-Host ''
Write-Host "[OK] $Team Brain '$Name' is active. Double-click START.cmd." -ForegroundColor Green
