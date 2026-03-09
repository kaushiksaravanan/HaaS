# Quick Start Guide - HANA Sentinel

Get up and running in 5 minutes!

## 1. Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install frontend packages
cd frontend
npm install
cd ..
```

## 2. Start Development Servers

### Windows
```powershell
.\dev.ps1
```

### Linux/Mac
```bash
chmod +x dev.sh
./dev.sh
```

## 3. Access the Application

Open your browser:
- **Web UI**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

## 4. Explore Features

### Agent Flow
- Navigate to "Agent Flow" in the sidebar
- Click on agents to see details
- Explore the interactive architecture diagram

### Agent Chat
- Navigate to "Agent Chat"
- Type questions like:
  - "Check system health"
  - "Show backup status"
  - "Analyze SQL performance"

### Dashboard
- View real-time system metrics
- Monitor agent activity
- Check system status

### Incidents
- View active incidents
- Click for details
- Propose remediations

### Risk Budget
- Monitor budget utilization
- View transaction history
- Check policy rules

## 5. Deploy to Google App Engine

```bash
# Windows
.\deploy_frontend.ps1

# Linux/Mac
./deploy_frontend.sh
```

Your app will be live at: `https://your-project.appspot.com`

## Common Issues

### Port Already in Use
If port 3000 or 8000 is busy:
- Kill the process using the port
- Or change the port in `frontend/vite.config.js`

### HANA Connection Failed
Running in demo mode without HANA:
- The app will work with mock data
- Some features will show "demo mode" message

### Build Errors
Clear caches:
```bash
cd frontend
rm -rf node_modules dist
npm install
npm run build
```

## Next Steps

1. Configure your HANA connection in `.env`
2. Configure the remote exec server URL in `.env`
3. Configure Google Cloud project
4. Enable RAG knowledge base
5. Customize risk policies

## Need Help?

- Check [README_FRONTEND.md](README_FRONTEND.md) for full documentation
- Review API docs at http://localhost:8000/docs
- Check `frontend/README.md` for frontend details
