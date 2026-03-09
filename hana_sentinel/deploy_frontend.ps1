# Build and Deploy Script for Google App Engine (Windows)

Write-Host "HANA Sentinel - Build & Deploy to Google App Engine" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Step 1: Install frontend dependencies
Write-Host ""
Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location frontend
npm install

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install frontend dependencies" -ForegroundColor Red
    exit 1
}

# Step 2: Build frontend
Write-Host ""
Write-Host "Building React frontend..." -ForegroundColor Yellow
npm run build

if ($LASTEXITCODE -ne 0) {
    Write-Host "Frontend build failed" -ForegroundColor Red
    exit 1
}

# Verify build
if (-not (Test-Path "dist")) {
    Write-Host "Frontend build failed - dist directory not found" -ForegroundColor Red
    exit 1
}

Write-Host "Frontend built successfully" -ForegroundColor Green
Set-Location ..

# Step 3: Install Python dependencies
Write-Host ""
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install Python dependencies" -ForegroundColor Red
    exit 1
}

# Step 4: Deploy to Google App Engine
Write-Host ""
Write-Host "Deploying to Google App Engine..." -ForegroundColor Yellow
gcloud app deploy app.yaml

if ($LASTEXITCODE -ne 0) {
    Write-Host "Deployment failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Your application is now available at:" -ForegroundColor Cyan
gcloud app browse --no-launch-browser
