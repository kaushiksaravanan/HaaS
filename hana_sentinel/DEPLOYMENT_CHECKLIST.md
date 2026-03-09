# Deployment Checklist

Complete checklist for deploying HANA Sentinel to Google App Engine.

## Pre-Deployment

### 1. Environment Setup
- [ ] Google Cloud SDK installed
- [ ] Node.js 18+ installed
- [ ] Python 3.11+ installed
- [ ] Git repository initialized
- [ ] Project authenticated with `gcloud auth login`
- [ ] Correct GCP project set: `gcloud config set project YOUR_PROJECT`

### 2. Configuration Files
- [ ] `.env` file created with all required variables
- [ ] `app.yaml` has correct project settings
- [ ] Environment variables in `app.yaml` are up to date
- [ ] HANA connection details configured
- [ ] Remote exec server URL configured
- [ ] Google Cloud project ID is correct

### 3. Frontend Setup
- [ ] `cd frontend && npm install` completed successfully
- [ ] No errors in package installation
- [ ] `npm run dev` works locally
- [ ] All pages load without errors
- [ ] API calls work with backend

### 4. Backend Setup
- [ ] `pip install -r requirements.txt` completed
- [ ] No dependency conflicts
- [ ] `python main.py api` starts successfully
- [ ] API docs accessible at `/docs`
- [ ] Health endpoint returns 200

## Build Phase

### 5. Frontend Build
- [ ] `cd frontend && npm run build` runs successfully
- [ ] `dist/` folder created
- [ ] `dist/index.html` exists
- [ ] `dist/assets/` contains JS and CSS files
- [ ] No build warnings or errors
- [ ] Build size is reasonable (<5MB recommended)

### 6. Local Testing
- [ ] Built frontend previews correctly: `npm run preview`
- [ ] All routes work in preview
- [ ] API integration works
- [ ] No console errors in browser
- [ ] Images and assets load correctly

## Deployment Phase

### 7. Pre-Deployment Checks
- [ ] Current directory is project root
- [ ] `frontend/dist/` folder exists and is populated
- [ ] `app.yaml` is in project root
- [ ] `.gcloudignore` is configured
- [ ] No uncommitted sensitive data in code

### 8. App Engine Setup
- [ ] App Engine enabled in GCP project: `gcloud app create`
- [ ] Region selected (e.g., us-central1)
- [ ] Billing enabled on GCP project
- [ ] Sufficient quota available

### 9. Deploy Application
- [ ] Run deployment script:
  - Windows: `.\deploy_frontend.ps1`
  - Linux/Mac: `./deploy_frontend.sh`
- [ ] No errors during deployment
- [ ] Deployment completes successfully
- [ ] Service URL provided

### 10. Verify Deployment
- [ ] App accessible at provided URL
- [ ] Home page loads
- [ ] All navigation links work
- [ ] Static assets load (check Network tab)
- [ ] API endpoints respond correctly
- [ ] No 404 errors for routes

## Post-Deployment

### 11. Functional Testing
- [ ] Dashboard shows data
- [ ] Agent Flow visualization renders
- [ ] Agent Chat interface loads
- [ ] Incidents page displays
- [ ] Risk Budget page works
- [ ] Monitoring page shows metrics
- [ ] Navigation between pages works

### 12. API Testing
- [ ] `/api/v1/health` returns 200
- [ ] `/api/v1/incidents` returns data
- [ ] `/api/v1/agents` returns agent list
- [ ] `/api/v1/risk-budgets/HXE` returns budget
- [ ] Chat endpoint responds
- [ ] No CORS errors

### 13. Performance Check
- [ ] Page load time < 3 seconds
- [ ] No JavaScript errors in console
- [ ] Assets load from CDN/static handler
- [ ] API response time < 1 second
- [ ] No memory leaks

### 14. Security Verification
- [ ] No sensitive data in client-side code
- [ ] Environment variables not exposed
- [ ] HTTPS enabled (GAE default)
- [ ] API authentication implemented (if required)
- [ ] CORS properly configured

### 15. Monitoring Setup
- [ ] Cloud Logging enabled
- [ ] Error reporting configured
- [ ] Performance monitoring active
- [ ] Uptime checks configured (optional)
- [ ] Alerts configured (optional)

## Troubleshooting

### If Deployment Fails

#### Build Errors
- [ ] Check Node.js version: `node --version`
- [ ] Clear npm cache: `npm cache clean --force`
- [ ] Delete and reinstall: `rm -rf node_modules && npm install`
- [ ] Check for TypeScript errors
- [ ] Verify all imports are correct

#### Deployment Errors
- [ ] Check `gcloud` authentication: `gcloud auth list`
- [ ] Verify project: `gcloud config get-value project`
- [ ] Check quotas in GCP console
- [ ] Review deployment logs: `gcloud app logs tail`
- [ ] Verify `app.yaml` syntax

#### Runtime Errors
- [ ] Check App Engine logs: `gcloud app logs read`
- [ ] Verify environment variables
- [ ] Test HANA connection
- [ ] Check remote exec server access
- [ ] Verify file permissions

#### 404 Errors
- [ ] Verify `frontend/dist` was deployed
- [ ] Check handlers in `app.yaml`
- [ ] Verify static file paths
- [ ] Check React Router configuration

#### API Errors
- [ ] Test API locally first
- [ ] Check CORS configuration
- [ ] Verify API base URL
- [ ] Check request/response format
- [ ] Review FastAPI logs

## Rollback Procedure

If deployment fails:

1. List versions:
   ```bash
   gcloud app versions list
   ```

2. Route traffic to previous version:
   ```bash
   gcloud app services set-traffic default --splits PREVIOUS_VERSION=1
   ```

3. Delete failed version:
   ```bash
   gcloud app versions delete FAILED_VERSION
   ```

## Success Criteria

✅ Deployment is successful when:
- [ ] Application loads at GAE URL
- [ ] All pages are accessible
- [ ] Navigation works smoothly
- [ ] API calls succeed
- [ ] No errors in browser console
- [ ] No errors in GAE logs
- [ ] Performance is acceptable
- [ ] All features work as expected

## Documentation

- [ ] Update README with deployment URL
- [ ] Document any configuration changes
- [ ] Update team on deployment
- [ ] Note any issues encountered
- [ ] Document resolution steps

## Regular Maintenance

Schedule these tasks:

### Daily
- [ ] Check error logs
- [ ] Monitor performance
- [ ] Verify uptime

### Weekly
- [ ] Review resource usage
- [ ] Check for security updates
- [ ] Update dependencies if needed

### Monthly
- [ ] Performance audit
- [ ] Security review
- [ ] Cost optimization review

---

## Quick Commands

```bash
# Deploy
./deploy_frontend.sh  # or .ps1 on Windows

# Check status
gcloud app browse
gcloud app describe

# View logs
gcloud app logs tail

# List versions
gcloud app versions list

# SSH to instance (for debugging)
gcloud app instances ssh $(gcloud app instances list --format='value(id)' | head -n1)
```

---

Date Deployed: ________________
Deployed By: ________________
Version: ________________
URL: ________________
Notes: ________________
