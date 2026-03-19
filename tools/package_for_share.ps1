# package_for_share.ps1
# Create a clean share ZIP on the current user's Desktop that excludes the `backups` folder
# and common caches. The resulting ZIP contains a small `run.ps1` and `run.bat` so the
# recipient can unzip and run with minimal steps.

param(
    [string]$OutputZip = "$env:USERPROFILE\Desktop\NEA-Project-1-share.zip",
    [string]$Staging = "$env:TEMP\NEA-Project-1-share"
)

$proj = (Get-Location).Path
Write-Host "Project: $proj"
Write-Host "Staging: $Staging"
Write-Host "Output: $OutputZip"

if (Test-Path $Staging) { Remove-Item $Staging -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Path $Staging | Out-Null

# Copy project excluding heavy or local-only folders
# Exclude: .venv, backups, .git, __pycache__, *.pyc, .vscode
robocopy $proj $Staging /E /XD .venv backups .git __pycache__ .pytest_cache .mypy_cache .vscode /XF *.pyc > $null

# Create a simple PowerShell run script for recipients
$runPs = @'
# run.ps1 - Bootstraps venv, installs requirements and runs the app.
param()
$ErrorActionPreference = 'Stop'
if (-not (Test-Path .venv)) {
    Write-Host "Creating virtual environment..."
    py -3 -m venv .venv
}
$pyexe = Join-Path -Path (Get-Location) -ChildPath ".venv\Scripts\python.exe"
if (-not (Test-Path $pyexe)) {
    Write-Error "Python executable not found in .venv. Ensure Python 3.10+ (or appropriate) is installed and 'py' launcher is available."
    exit 1
}
Write-Host "Upgrading pip and installing requirements..."
& $pyexe -m pip install --upgrade pip | Out-Null
& $pyexe -m pip install -r requirements.txt | Out-Null
Write-Host "Launching application..."
Start-Process -FilePath $pyexe -ArgumentList 'src\pathfinder\app.py' -NoNewWindow
'@

$runPsPath = Join-Path $Staging 'run.ps1'
$runPs | Out-File -FilePath $runPsPath -Encoding UTF8

# Create a simple Windows batch runner for convenience
$runBat = @'
@echo off
REM run.bat - bootstraps venv (if needed), installs requirements, and runs app
if not exist .venv (py -3 -m venv .venv)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe src\pathfinder\app.py
'@
$runBatPath = Join-Path $Staging 'run.bat'
$runBat | Out-File -FilePath $runBatPath -Encoding ASCII

# Create the zip
if (Test-Path $OutputZip) { Remove-Item $OutputZip -Force -ErrorAction SilentlyContinue }
Compress-Archive -Path "$Staging\*" -DestinationPath $OutputZip -CompressionLevel Optimal

# Cleanup staging
Remove-Item $Staging -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Created package: $OutputZip"
