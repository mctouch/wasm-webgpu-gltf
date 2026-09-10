# deploy-iis.ps1 — Deploy the WebGPU glTF viewer to IIS on Windows 11
# Run as Administrator in PowerShell

$ErrorActionPreference = "Stop"

# --- Config ---
$SiteName = "WebGPU-gltf"
$Port = 8080
$SourceDir = $PSScriptRoot + "\www"
$DestDir = "C:\inetpub\wwwroot\webgpu-gltf"

Write-Host "=== Deploying WebGPU glTF Viewer to IIS ===" -ForegroundColor Cyan

# --- Check admin ---
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(`
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: Run this script as Administrator." -ForegroundColor Red
    exit 1
}

# --- Check IIS is installed ---
Import-Module WebAdministration -ErrorAction SilentlyContinue
if (-not (Get-Module WebAdministration)) {
    Write-Host "IIS is not installed. Run:" -ForegroundColor Yellow
    Write-Host "  Enable-WindowsOptionalFeature -Online -FeatureName IIS-WebServerRole" -ForegroundColor Gray
    exit 1
}

# --- Copy files ---
Write-Host "Copying files to $DestDir ..." -ForegroundColor Green
if (Test-Path $DestDir) { Remove-Item $DestDir -Recurse -Force }
New-Item -ItemType Directory -Path $DestDir -Force | Out-Null
Copy-Item -Path "$SourceDir\*" -Destination $DestDir -Recurse -Force

Write-Host "Files copied:" -ForegroundColor Gray
Get-ChildItem $DestDir -Recurse | ForEach-Object {
    $rel = $_.FullName.Replace($DestDir, "")
    Write-Host "  $rel"
}

# --- Create IIS site ---
$existingSite = Get-Website -Name $SiteName -ErrorAction SilentlyContinue
if ($existingSite) {
    Write-Host "Removing existing site '$SiteName' ..." -ForegroundColor Yellow
    Remove-Website -Name $SiteName
}

$existingPool = Get-Item "IIS:\AppPools\$SiteName" -ErrorAction SilentlyContinue
if ($existingPool) {
    Remove-Item "IIS:\AppPools\$SiteName" -Recurse
}

Write-Host "Creating IIS site '$SiteName' on port $Port ..." -ForegroundColor Green
New-WebAppPool -Name $SiteName | Out-Null
New-Website -Name $SiteName `
    -Port $Port `
    -PhysicalPath $DestDir `
    -ApplicationPool $SiteName | Out-Null

# --- Verify ---
$site = Get-Website -Name $SiteName
if ($site) {
    Write-Host ""
    Write-Host "=== Deploy successful ===" -ForegroundColor Green
    Write-Host "Site:   $SiteName" -ForegroundColor White
    Write-Host "URL:    http://localhost:$Port" -ForegroundColor White
    Write-Host "Path:   $DestDir" -ForegroundColor White
    Write-Host ""
    Write-Host "Open in Chrome or Edge (WebGPU required):" -ForegroundColor Cyan
    Write-Host "  http://localhost:$Port" -ForegroundColor White
    Write-Host ""

    # Open browser
    Start-Process "http://localhost:$Port"
} else {
    Write-Host "ERROR: Failed to create IIS site." -ForegroundColor Red
    exit 1
}
