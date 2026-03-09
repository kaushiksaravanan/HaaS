# Common Commands Reference

Quick reference for common tasks in HANA Sentinel.

## Development

### Start Both Frontend and Backend
```bash
# Windows
.\dev.ps1

# Linux/Mac
./dev.sh
```

### Start Backend Only
```bash
python main.py api
```

### Start Frontend Only
```bash
cd frontend
npm run dev
```

### View API Documentation
```
http://localhost:8000/docs
```

## Building

### Build Frontend for Production
```bash
cd frontend
npm run build
```

### Preview Production Build
```bash
cd frontend
npm run preview
```

## Deployment

### Deploy to Google App Engine
```bash
# Windows
.\deploy_frontend.ps1

# Linux/Mac
./deploy_frontend.sh
```

### Manual Deployment
```bash
cd frontend
npm run build
cd ..
gcloud app deploy app.yaml
```

### View Deployed App
```bash
gcloud app browse
```

### View Deployment Logs
```bash
gcloud app logs tail -s default
```

## Testing

### Verify System Setup
```bash
python main.py verify
```

### Run Chaos Engineering Tests
```bash
python main.py chaos
```

## Maintenance

### Update Frontend Dependencies
```bash
cd frontend
npm update
```

### Update Python Dependencies
```bash
pip install -r requirements.txt --upgrade
```

### Clean Build Artifacts
```bash
# Frontend
cd frontend
rm -rf node_modules dist
npm install

# Python
find . -type d -name __pycache__ -exec rm -rf {} +
```

## Troubleshooting

### Port Already in Use
```bash
# Windows - Kill process on port 8000
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process

# Linux/Mac - Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

### Clear npm Cache
```bash
npm cache clean --force
```

### Rebuild from Scratch
```bash
# Frontend
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

## Google Cloud

### Set Active Project
```bash
gcloud config set project YOUR_PROJECT_ID
```

### View App Engine Services
```bash
gcloud app services list
```

### View App Engine Versions
```bash
gcloud app versions list
```

### Connect to App Engine Instance
```bash
gcloud app instances list
```

### View Environment Variables
```bash
gcloud app describe
```

## Git Operations

### Initial Commit
```bash
git add .
git commit -m "Add React frontend with agent visualization"
git push
```

### Ignore Frontend Build
```bash
# Already configured in .gitignore
echo "frontend/dist" >> .gitignore
echo "frontend/node_modules" >> .gitignore
```

## Quick Health Checks

### Test Backend Health
```bash
curl http://localhost:8000/api/v1/health
```

### Test Frontend Build
```bash
cd frontend
npm run build
cd dist
python -m http.server 8080
# Visit http://localhost:8080
```

### Test API Endpoints
```bash
# List incidents
curl http://localhost:8000/api/v1/incidents

# Get risk budget
curl http://localhost:8000/api/v1/risk-budgets/HXE

# List agents
curl http://localhost:8000/api/v1/agents
```

## Environment

### Copy Environment Template
```bash
cp .env.example .env
```

### View Environment Variables (Production)
```bash
gcloud app describe --format="yaml(env_variables)"
```

## Logs

### View Backend Logs (Local)
```bash
python main.py api 2>&1 | tee app.log
```

### View Frontend Dev Logs
```bash
cd frontend
npm run dev 2>&1 | tee dev.log
```

### View GAE Logs
```bash
# Tail logs
gcloud app logs tail

# Read recent logs
gcloud app logs read --limit=50

# Filter by severity
gcloud app logs read --level=error
```

## Performance

### Analyze Bundle Size
```bash
cd frontend
npm run build
npx vite-bundle-visualizer
```

### Check Frontend Performance
```bash
cd frontend
npm run build
npx lighthouse http://localhost:3000 --view
```

## Useful Aliases

Add these to your shell profile:

```bash
# .bashrc or .zshrc
alias hana-dev="cd /path/to/hana_sentinel && ./dev.sh"
alias hana-deploy="cd /path/to/hana_sentinel && ./deploy_frontend.sh"
alias hana-logs="gcloud app logs tail -s default"
```

```powershell
# PowerShell profile
function hana-dev { cd C:\path\to\hana_sentinel; .\dev.ps1 }
function hana-deploy { cd C:\path\to\hana_sentinel; .\deploy_frontend.ps1 }
function hana-logs { gcloud app logs tail -s default }
```

## Quick Reference URLs

Local Development:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

Production (replace with your project):
- App: https://YOUR_PROJECT.appspot.com
- Logs: https://console.cloud.google.com/logs
- App Engine: https://console.cloud.google.com/appengine

## Emergency

### Stop All Local Services
```bash
# Kill all Python processes
pkill python

# Kill all Node processes  
pkill node
```

### Rollback GAE Deployment
```bash
# List versions
gcloud app versions list

# Traffic to previous version
gcloud app services set-traffic default --splits VERSION_ID=1
```

### Emergency Stop GAE
```bash
gcloud app versions stop VERSION_ID
```

---

For more details, see:
- [QUICKSTART.md](QUICKSTART.md)
- [README_FRONTEND.md](README_FRONTEND.md)
- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)
