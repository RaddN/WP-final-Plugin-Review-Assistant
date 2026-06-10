# WP Plugin Review Assistant - Build Script for Windows
# Creates a standalone .exe file using PyInstaller

param(
    [switch]$Clean,
    [switch]$NoConsole = $true
)

Write-Host "WP Plugin Review Assistant - Build Script"
Write-Host "=========================================="
Write-Host ""

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Using: $pythonVersion"
} catch {
    Write-Host "ERROR: Python not found. Please install Python 3.9+" -ForegroundColor Red
    exit 1
}

# Check if PyInstaller is installed
Write-Host "Checking for PyInstaller..."
try {
    python -c "import PyInstaller; print('PyInstaller found')" >$null 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing PyInstaller..."
        pip install pyinstaller
    }
} catch {
    Write-Host "Installing PyInstaller..."
    pip install pyinstaller
}

# Clean previous builds
if ($Clean) {
    Write-Host "Cleaning previous builds..."
    if (Test-Path ".\build") { Remove-Item -Recurse -Force ".\build" }
    if (Test-Path ".\dist") { Remove-Item -Recurse -Force ".\dist" }
    if (Test-Path "*.spec") { Remove-Item -Force "*.spec" }
}

# Build the executable
Write-Host ""
Write-Host "Building standalone executable..."
Write-Host "This may take a few minutes..."
Write-Host ""

$pyinstallerArgs = @(
    "--onefile"
    "--name=WP-Plugin-Review-Assistant"
    "--version-file=version.txt"
    "--paths=src"
    "--add-data=src:src"
    "main.py"
)

if (Test-Path ".\icon.ico") {
    $pyinstallerArgs += "--icon=icon.ico"
} else {
    Write-Host "icon.ico not found; building with the default application icon." -ForegroundColor Yellow
}

if ($NoConsole) {
    $pyinstallerArgs += "--windowed"
}

& python -m PyInstaller @pyinstallerArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "Build successful!" -ForegroundColor Green
    Write-Host "=========================================="
    Write-Host ""
    Write-Host "Executable location: .\dist\WP-Plugin-Review-Assistant.exe"
    Write-Host ""
    Write-Host "You can now run the application by executing the .exe file directly."
    Write-Host "Python is bundled; LocalWP and WP-CLI are still required for site reviews."
} else {
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "Build failed!" -ForegroundColor Red
    Write-Host "=========================================="
    exit 1
}
