<#
.SYNOPSIS
Build a Windows GUI distribution of NoteManager with PyInstaller.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1 -OutputDir C:\Release
#>

[CmdletBinding()]
param(
    [string]$OutputDir = "",
    [switch]$InstallBuildDependencies
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $OutputDir) {
    $OutputDir = Join-Path $projectRoot "dist"
}

$buildRoot = Join-Path $projectRoot "build\pyinstaller"
$iconPath = Join-Path $projectRoot "src\gui\assets\notemanager.ico"
$assetPath = Join-Path $projectRoot "src\gui\assets"
$dataPath = Join-Path $projectRoot "data"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Install Python 3.10+ and add it to PATH."
}

if ($InstallBuildDependencies) {
    & python -m pip install -r (Join-Path $projectRoot "requirements.txt") PyInstaller
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install build dependencies."
    }
}

& python -c "import PyInstaller, frontmatter, jieba, PyQt6"
if ($LASTEXITCODE -ne 0) {
    throw "Missing build dependencies. Run this script again with -InstallBuildDependencies."
}

& python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name NoteManager `
    --icon $iconPath `
    --add-data "$assetPath;src\gui\assets" `
    --add-data "$dataPath;data" `
    --collect-submodules src `
    --distpath $OutputDir `
    --workpath (Join-Path $buildRoot "work") `
    --specpath (Join-Path $buildRoot "spec") `
    (Join-Path $projectRoot "main.py")

if ($LASTEXITCODE -ne 0) {
    throw "Packaging failed."
}

Write-Host "Build completed: $(Join-Path $OutputDir 'NoteManager\\NoteManager.exe')"
