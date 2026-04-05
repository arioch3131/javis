[CmdletBinding()]
param(
    [switch]$RunApp,
    [switch]$SkipMagicFallback,
    [int]$PipRetries = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $true
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$FriendlyName = $FilePath,
        [switch]$AllowFailure
    )

    Write-Host ("   {0} {1}" -f $FilePath, ($Arguments -join " ")) -ForegroundColor DarkGray
    & $FilePath @Arguments
    $exitCode = $LASTEXITCODE
    if (($null -ne $exitCode) -and ($exitCode -ne 0) -and (-not $AllowFailure)) {
        throw "$FriendlyName failed with exit code $exitCode"
    }

    return $exitCode
}

function Invoke-PipWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe,
        [Parameter(Mandatory = $true)]
        [string[]]$PipArgs,
        [int]$Retries = 2
    )

    for ($attempt = 0; $attempt -le $Retries; $attempt++) {
        try {
            Invoke-CheckedCommand -FilePath $PythonExe -Arguments (@("-m", "pip") + $PipArgs) -FriendlyName "pip $($PipArgs -join ' ')"
            return
        } catch {
            if ($attempt -ge $Retries) {
                throw
            }
            $delaySeconds = [Math]::Min(10, 2 * ($attempt + 1))
            Write-Host "pip command failed, retrying in $delaySeconds second(s)..." -ForegroundColor Yellow
            Start-Sleep -Seconds $delaySeconds
        }
    }
}

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            Invoke-CheckedCommand -FilePath "py" -Arguments @("-3.11", "-c", "import sys; assert sys.version_info >= (3,11)") -FriendlyName "Python version check (py)"
            return @{
                Exe = "py"
                Args = @("-3.11")
            }
        } catch {
            throw "Python 3.11+ not found via 'py'. Install Python 3.11 or newer."
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        try {
            Invoke-CheckedCommand -FilePath "python" -Arguments @("-c", "import sys; assert sys.version_info >= (3,11)") -FriendlyName "Python version check (python)"
            return @{
                Exe = "python"
                Args = @()
            }
        } catch {
            throw "Found 'python' but version is < 3.11. Install Python 3.11 or newer."
        }
    }

    throw "Python not found. Install Python 3.11+ and reopen PowerShell."
}

$projectRoot = Split-Path -Parent $PSCommandPath
Set-Location $projectRoot

if (-not (Test-Path (Join-Path $projectRoot "pyproject.toml"))) {
    throw "pyproject.toml not found in $projectRoot. Run this script from the project root copy."
}
if (-not (Test-Path (Join-Path $projectRoot "src\ai_content_classifier\main.py"))) {
    throw "src\ai_content_classifier\main.py not found. Project layout is incomplete."
}

Write-Step "Checking Python"
$pythonCmd = Get-PythonCommand

Write-Step "Creating virtual environment (.venv)"
if (-not (Test-Path ".venv")) {
    Invoke-CheckedCommand -FilePath $pythonCmd.Exe -Arguments (@($pythonCmd.Args) + @("-m", "venv", ".venv")) -FriendlyName "Create virtual environment"
} else {
    Write-Host ".venv already exists, reusing it."
}

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Virtual environment python not found at $venvPython"
}

Write-Step "Upgrading pip/setuptools/wheel"
Invoke-PipWithRetry -PythonExe $venvPython -PipArgs @("install", "--upgrade", "pip", "setuptools", "wheel") -Retries $PipRetries

Write-Step "Installing project in editable mode"
Invoke-PipWithRetry -PythonExe $venvPython -PipArgs @("install", "-e", ".") -Retries $PipRetries

if (-not $SkipMagicFallback) {
    Write-Step "Applying Windows compatibility fallback for python-magic"
    try {
        Invoke-PipWithRetry -PythonExe $venvPython -PipArgs @("uninstall", "-y", "python-magic") -Retries 0
        Invoke-PipWithRetry -PythonExe $venvPython -PipArgs @("install", "python-magic-bin") -Retries $PipRetries
        Write-Host "Installed python-magic-bin (Windows fallback)."
    } catch {
        Write-Host "Skipped python-magic-bin fallback (not critical)." -ForegroundColor Yellow
    }
} else {
    Write-Host "Skipping python-magic fallback as requested."
}

Write-Step "Installation completed"
Write-Host "To run the app:"
Write-Host "  .\.venv\Scripts\python.exe src\ai_content_classifier\main.py"
Write-Host ""
Write-Host "Or activate the venv first:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  python src\ai_content_classifier\main.py"

if ($RunApp) {
    Write-Step "Running application"
    Invoke-CheckedCommand -FilePath $venvPython -Arguments @("src\ai_content_classifier\main.py") -FriendlyName "Run application"
}
