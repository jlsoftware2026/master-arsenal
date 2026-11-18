$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

$Python = (Get-Command python -ErrorAction Stop).Source
$DistRoot = Join-Path $RepoRoot "dist\payload"
$BuildRoot = Join-Path $RepoRoot "build\pyinstaller"

if (Test-Path $DistRoot) { Remove-Item $DistRoot -Recurse -Force }
if (Test-Path $BuildRoot) { Remove-Item $BuildRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $DistRoot | Out-Null

& $Python -m pip install --disable-pip-version-check -e .
if ($LASTEXITCODE -ne 0) { throw "Project dependency installation failed." }

& $Python -m pip install --disable-pip-version-check "pyinstaller==6.11.1"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller installation failed." }

$CommonArgs = @("--noconfirm", "--clean", "--onedir", "--distpath", $DistRoot, "--workpath", $BuildRoot, "--collect-all", "reportlab", "--collect-all", "pymupdf", "--collect-all", "exchange_calendars", "--collect-all", "tzdata")

& $Python -m PyInstaller @CommonArgs --name "ma-local" --add-data "docs;docs" --add-data "skills;skills" --add-data "artifacts;artifacts" "packaging\windows\ma_local_entry.py"
if ($LASTEXITCODE -ne 0) { throw "Local Engine packaging failed." }

& $Python -m PyInstaller @CommonArgs --name "ma-binance" "packaging\windows\ma_binance_entry.py"
if ($LASTEXITCODE -ne 0) { throw "Binance Data Engine packaging failed." }

$LocalExe = Join-Path $DistRoot "ma-local\ma-local.exe"
$BinanceExe = Join-Path $DistRoot "ma-binance\ma-binance.exe"
foreach ($Exe in @($LocalExe, $BinanceExe)) {
    if (-not (Test-Path $Exe)) { throw "Expected packaged executable is missing: $Exe" }
}

& $LocalExe --help
if ($LASTEXITCODE -ne 0) { throw "Packaged Local Engine help smoke test failed." }
& $BinanceExe --help
if ($LASTEXITCODE -ne 0) { throw "Packaged Binance Engine help smoke test failed." }

$SmokeWorkspace = Join-Path $env:TEMP ("ma-packaging-smoke-" + [guid]::NewGuid().ToString("N"))
& $LocalExe --workspace $SmokeWorkspace init
if ($LASTEXITCODE -ne 0) { throw "Packaged Local Engine workspace initialization failed." }
if (-not (Test-Path (Join-Path $SmokeWorkspace "jobs\inbox"))) {
    throw "Packaged Local Engine did not create its expected workspace structure."
}

Write-Host "Windows packaging smoke tests passed."
