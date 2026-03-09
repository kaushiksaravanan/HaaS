# Local Development Script - Run Frontend and Backend concurrently (Windows)

Write-Host "🚀 Starting HANA Sentinel Development Environment" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# Start Backend in new window
Write-Host ""
Write-Host "🐍 Starting FastAPI backend on port 8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python main.py api"

# Wait for backend to start
Start-Sleep -Seconds 3

# Start Frontend in new window
Write-Host ""
Write-Host "⚛️  Starting React frontend on port 3000..." -ForegroundColor Yellow
Set-Location frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev"
Set-Location ..

Write-Host ""
Write-Host "✅ Development environment is starting!" -ForegroundColor Green
Write-Host ""
Write-Host "📖 Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "📖 Backend API: http://localhost:8000" -ForegroundColor Cyan
Write-Host "📖 API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Close the PowerShell windows to stop the services" -ForegroundColor Yellow
