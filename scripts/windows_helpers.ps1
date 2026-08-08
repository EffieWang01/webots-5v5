function Convert-ToWslPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = (Resolve-Path -LiteralPath $Path).Path
    if ($resolved -notmatch '^([A-Za-z]):\\(.*)$') {
        throw "The project and Brain files must be on a local Windows drive: $resolved"
    }

    $drive = $Matches[1].ToLowerInvariant()
    $rest = $Matches[2].Replace('\', '/')
    return "/mnt/$drive/$rest"
}

function Convert-ToBashLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    $quote = [string][char]39
    $escapedQuote = $quote + '"' + $quote + '"' + $quote
    return $quote + $Value.Replace($quote, $escapedQuote) + $quote
}

function Assert-WslDistro {
    param([Parameter(Mandatory = $true)][string]$Distro)

    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    $probe = (& wsl.exe -d $Distro -- sh -lc 'printf WEBOTS_SIM_WSL_READY' 2>&1 | Out-String)
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $savedPreference

    if ($exitCode -ne 0 -or $probe -notmatch 'WEBOTS_SIM_WSL_READY') {
        throw "WSL distro '$Distro' is unavailable. Install it with: wsl --install -d $Distro"
    }
}

function Find-WebotsExecutable {
    param([string]$ExplicitPath)

    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        $candidates += $ExplicitPath
    }
    if (-not [string]::IsNullOrWhiteSpace($env:WEBOTS_HOME)) {
        $candidates += (Join-Path $env:WEBOTS_HOME 'msys64\mingw64\bin\webots.exe')
        $candidates += (Join-Path $env:WEBOTS_HOME 'webots.exe')
    }
    $candidates += 'C:\Program Files\Webots\msys64\mingw64\bin\webots.exe'
    $candidates += 'C:\Program Files\Webots\webots.exe'

    $fromPath = Get-Command webots.exe -ErrorAction SilentlyContinue
    if ($null -ne $fromPath) {
        $candidates += $fromPath.Source
    }

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw 'Webots was not found. Install Webots, or pass -WebotsPath "C:\...\webots.exe".'
}

function Find-PythonExecutable {
    $candidates = @()
    $fromPath = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -ne $fromPath) {
        $candidates += $fromPath.Source
    }
    $candidates += Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python*\python.exe') -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty FullName
    $candidates += Get-ChildItem -Path (Join-Path $env:ProgramFiles 'Python*\python.exe') -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty FullName

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $output = (& $candidate --version 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and $output -match 'Python\s+(\d+)\.(\d+)') {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
                return (Resolve-Path -LiteralPath $candidate).Path
            }
        }
    }

    throw 'Python 3.10 or newer was not found. Install 64-bit Python for Windows and select "Add python.exe to PATH".'
}
