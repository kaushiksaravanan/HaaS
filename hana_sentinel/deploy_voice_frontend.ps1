#!/usr/bin/env pwsh
# Deploy HANA Sentinel Voice Frontend to Vercel
# Usage: .\deploy_voice_frontend.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== HANA Sentinel Voice Frontend — Vercel Deploy ===" -ForegroundColor Green

# Check if vercel CLI is installed
if (-not (Get-Command vercel -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Vercel CLI..." -ForegroundColor Yellow
    npm install -g vercel
}

Push-Location "$PSScriptRoot\voice_frontend"

try {
    # Install dependencies
    Write-Host "`nInstalling dependencies..." -ForegroundColor Cyan
    npm install

    # Build
    Write-Host "`nBuilding..." -ForegroundColor Cyan
    npx next build

    # Deploy
    Write-Host "`nDeploying to Vercel..." -ForegroundColor Cyan
    Write-Host "Make sure to set these env vars in the Vercel dashboard:" -ForegroundColor Yellow
    Write-Host "  LIVEKIT_URL"
    Write-Host "  LIVEKIT_API_KEY"
    Write-Host "  LIVEKIT_API_SECRET"
    Write-Host ""

    vercel --prod

    Write-Host "`nDone! Your voice interface is live." -ForegroundColor Green
}
finally {
    Pop-Location
}
