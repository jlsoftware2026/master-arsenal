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

$LockPath = Join-Path $DistRoot "runtime-lock.txt"
$LockLines = & $Python -m pip freeze --all
if ($LASTEXITCODE -ne 0) { throw "Could not capture the packaged runtime dependency inventory." }
$LockLines | Set-Content -Path $LockPath -Encoding utf8

$PyInstallerVersion = (& $Python -m PyInstaller --version).Trim()
$PythonVersion = (& $Python --version).Trim()
$PayloadFiles = Get-ChildItem $DistRoot -File -Recurse | Where-Object { $_.Name -ne "release-manifest.json" }
$FileRecords = @()
foreach ($File in $PayloadFiles) {
    $RelativePath = $File.FullName.Substring($DistRoot.Length + 1).Replace("\\", "/")
    $FileRecords += [ordered]@{
        path = $RelativePath
        size_bytes = $File.Length
        sha256 = (Get-FileHash $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$Manifest = [ordered]@{
    schema_version = 1
    application = "MASTER ARSENAL"
    application_version = "0.3.0"
    source_commit = $env:GITHUB_SHA
    target = "Windows x64; Windows 10 22H2 / Windows 11 compatibility target"
    python = $PythonVersion
    pyinstaller = $PyInstallerVersion
    java_runtime = "not bundled: current repository has no Java source or JAR component"
    dependency_lock = "runtime-lock.txt"
    files = $FileRecords
}
$Manifest | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $DistRoot "release-manifest.json") -Encoding utf8

Write-Host "Windows packaging smoke tests passed."
