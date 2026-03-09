# Testing Guide - HANA Sentinel Real-Time Animations

This guide explains how to test the complete React frontend with real-time animations, colorful designs, and parameter change visualizations.

## Prerequisites

Before testing, ensure you have:
- ✅ Node.js 16+ installed
- ✅ Python 3.11+ installed
- ✅ All dependencies installed

## Step 1: Install Dependencies

### Frontend Dependencies

```powershell
cd frontend
npm install
```

This will install all required packages including:
- `framer-motion` - Smooth animations
- `react-hot-toast` - Toast notifications
- `react-confetti` - Celebration effects
- `react-flow` - Agent flow visualization
- `recharts` - Data charts

### Backend Dependencies

```powershell
cd ..
pip install -r requirements.txt
```

## Step 2: Start Development Servers

### Option A: Using Development Scripts (Recommended)

**Windows:**
```powershell
.\dev.ps1
```

**Linux/Mac:**
```bash
chmod +x dev.sh
./dev.sh
```

This automatically starts both backend and frontend servers.

### Option B: Manual Start

**Terminal 1 - Backend:**
```powershell
python main.py api
```

**Terminal 2 - Frontend:**
```powershell
cd frontend
npm run dev
```

## Step 3: Access the Application

Open your browser and navigate to:
```
http://localhost:5173
```

The Vite dev server will automatically proxy API requests to the backend at `http://localhost:8080`.

## Step 4: Test Real-Time Features

### Dashboard Page

1. **Navigate to Dashboard** (home page)
2. **Observe Real-Time Metrics:**
   - Metric cards update every 3 seconds
   - Values animate with scale effects when they change
   - Progress bars fill based on threshold values
   - Trend arrows show up/down changes
   - Toast notifications appear for critical changes

3. **Watch Live Activity Stream:**
   - Activities slide in from the right
   - Background flashes on new items
   - "NEW" badges appear on recent activities
   - Auto-updates every 5 seconds

4. **Check Parameter Change Visualizer:**
   - Parameter cards show real-time VM changes
   - Cards rotate in 3D on load
   - Progress bars animate during changes
   - Confetti 🎉 celebrates successful changes
   - Status indicators: Pending → Applying → Success

### Agent Flow Page

1. **Navigate to Agent Flow**
2. **Watch Animated Agent Architecture:**
   - Edges (connections) animate to show data flow
   - Blue glow travels along edges every 2 seconds
   - Nodes have gradient backgrounds
   - Status indicators pulse
   - Hover effects scale nodes

3. **Click on Agent Nodes:**
   - Details panel slides in from right
   - Smooth AnimatePresence transitions
   - Activity items fade in with stagger effect

### Monitoring Page

1. **Navigate to Monitoring**
2. **Check Real-Time Metrics:**
   - Live badge pulses in top-right
   - Metric cards update with smooth animations
   - Background flashes on value changes
   - Charts update in real-time with new data points
   - Gradient line charts with tooltips

3. **Change Refresh Interval:**
   - Test 2s, 5s, and 10s intervals
   - Observe update frequency changes

### Agent Chat Page

1. **Navigate to Agent Chat**
2. **Test AI Conversation:**
   - Type: "system health"
   - Type: "backup status"
   - Type: "optimize sql"
   - Messages animate in smoothly
   - Typing indicator shows while processing

### Incidents Page

1. **Navigate to Incidents**
2. **Create New Incident:**
   - Click "Report Incident"
   - Fill in details
   - Submit and watch it appear in the list

### Risk Budget Page

1. **Navigate to Risk Budget**
2. **Check Budget Visualization:**
   - Risk budget gauge animates
   - Utilization percentage updates
   - Transaction history shows all actions

## Step 5: Test Backend API Endpoints

### Test Real-Time Metrics API

```bash
# Get real-time metrics
curl http://localhost:8080/api/v1/metrics/realtime

# Response includes:
# - cpu_usage
# - memory_usage
# - disk_usage
# - active_connections
# - transactions_per_sec
# - response_time_ms
# - risk_budget data
```

### Test Activities API

```bash
# Get recent activities
curl http://localhost:8080/api/v1/activities/recent?limit=10

# Response includes:
# - Recent incidents
# - Action certificates
# - Agent activities
```

### Test Metrics History

```bash
# Get last 24 hours of metrics
curl http://localhost:8080/api/v1/metrics/history?hours=24
```

## Step 6: Verify Animations

### ✅ Animation Checklist

- [ ] **Dashboard Metrics** - Cards scale on value change
- [ ] **Toast Notifications** - Appear for critical changes
- [ ] **Activity Stream** - Items slide in from right
- [ ] **Parameter Visualizer** - 3D rotation and confetti
- [ ] **Agent Flow Edges** - Blue glow travels along connections
- [ ] **Agent Nodes** - Gradient backgrounds and pulse effects
- [ ] **Details Panel** - Slides in/out smoothly
- [ ] **LiveMetricCard** - Flash background on change
- [ ] **Progress Bars** - Animate fill based on thresholds
- [ ] **Trend Indicators** - Up/down arrows with colors
- [ ] **Live Badge** - Pulses continuously
- [ ] **Chart Updates** - Smooth line transitions

## Step 7: Performance Testing

### Check Browser Console

Open DevTools (F12) and check:
- ✅ No JavaScript errors
- ✅ API requests succeed (200 status)
- ✅ Polling intervals work correctly
- ✅ No memory leaks (open Profile tab)

### Network Activity

Monitor Network tab:
- `/api/v1/metrics/realtime` - Called every 3s
- `/api/v1/activities/recent` - Called every 5s
- `/api/v1/health` - On demand

### CPU Usage

- Frontend should use minimal CPU when idle
- Animations should be smooth (60 FPS)
- No frame drops on metric updates

## Step 8: Mobile Responsiveness

Test on different screen sizes:
- Desktop (1920x1080)
- Tablet (768x1024)
- Mobile (375x667)

All layouts should adapt using Tailwind's responsive classes.

## Troubleshooting

### Frontend Won't Start

```powershell
# Clear node_modules and reinstall
rm -r -fo node_modules
rm package-lock.json
npm install
```

### Backend API Not Responding

```powershell
# Check if port 8080 is in use
netstat -ano | findstr :8080

# Kill the process if needed
taskkill /PID <PID> /F

# Restart backend
python main.py api
```

### Animations Not Working

1. Check browser console for errors
2. Verify `framer-motion` is installed: `npm list framer-motion`
3. Clear browser cache (Ctrl+Shift+Del)
4. Hard reload (Ctrl+F5)

### CORS Errors

If you see CORS errors:
1. Ensure backend is running on port 8080
2. Check `vite.config.js` proxy configuration
3. Restart both servers

## Expected Behavior

### Real-Time Updates

- **Dashboard metrics**: Update every 3 seconds
- **Activity stream**: New items every 5 seconds
- **Agent flow edges**: Animate every 2 seconds
- **Monitoring charts**: Add data point every interval

### Visual Effects

- **Scale animations**: 1 → 1.02 → 1 on change
- **Fade transitions**: 0.3s duration
- **Slide animations**: From right (-100%) to center (0%)
- **Pulse effects**: Scale 1 → 1.2 → 1 (2s loop)
- **Gradient shifts**: Background position animation
- **Confetti**: Triggered on "success" status

### Color Scheme

- **Gradients**: Cyan → Blue → Purple
- **Success**: Green (#10b981)
- **Warning**: Orange (#f97316)
- **Error**: Red (#ef4444)
- **Info**: Blue (#3b82f6)
- **Background**: Dark gray (#0a0a0a → #1a1a2e)

## Next Steps

After successful testing:

1. **Build for Production:**
   ```powershell
   cd frontend
   npm run build
   ```

2. **Deploy to Google App Engine:**
   ```powershell
   .\deploy_frontend.ps1
   ```

3. **Monitor Production:**
   - Check logs: `gcloud app logs tail`
   - View metrics in Google Cloud Console
   - Set up monitoring alerts

## Feedback

Report issues or suggestions:
- Check browser console errors
- Review network requests
- Test on different browsers (Chrome, Firefox, Edge)
- Document reproduction steps

---

**Happy Testing! 🚀**

The real-time visualizations with animations bring the HANA Sentinel platform to life!
