# HANA Sentinel - AI Operations Platform

🛡️ Autonomous Policy-Driven Multi-Agent AI for SAP HANA Operations

A comprehensive AI-powered operations platform for SAP HANA, featuring:
- Multi-agent autonomous operations
- Policy-driven risk management
- Real-time monitoring and incident response
- Interactive web UI with agent flow visualization
- Google ADK integration for intelligent decision-making

## Architecture

### Backend (Python + FastAPI)
- **Supervisor Agent**: Orchestrates all operations and enforces policies
- **Health Agent**: Monitors system health and performance
- **Backup Agent**: Manages backup operations
- **Recovery Agent**: Handles disaster recovery
- **SQL Tuning Agent**: Optimizes query performance
- **Capacity Agent**: Manages resource capacity
- **Security Agent**: Monitors security threats
- **Browser Agent**: Searches SAP documentation

### Frontend (React + Vite)
- **Agent Flow Visualization**: Interactive diagram of agent architecture
- **Agent Chat Interface**: Chat with AI agents using natural language
- **Incident Management**: Track and remediate system incidents
- **Risk Budget Dashboard**: Monitor autonomous operation budgets
- **Real-time Monitoring**: System metrics and performance tracking

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- Google Cloud SDK (for deployment)
- SAP HANA instance (or demo mode)

### Local Development

#### 1. Clone and Setup

```bash
cd hana_sentinel
pip install -r requirements.txt
```

#### 2. Configure Environment

Copy `.env.example` to `.env` and configure your settings:
- HANA connection details
- Google Cloud project
- SSH access credentials

#### 3. Run Development Environment

**Windows:**
```powershell
.\dev.ps1
```

**Linux/Mac:**
```bash
chmod +x dev.sh
./dev.sh
```

This will start:
- FastAPI backend on `http://localhost:8000`
- React frontend on `http://localhost:3000`

#### 4. Access the Application

- **Web UI**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **API**: http://localhost:8000/api/v1

### Manual Start (Alternative)

**Terminal 1 - Backend:**
```bash
python main.py api
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Deployment to Google App Engine

### Build and Deploy

**Windows:**
```powershell
.\deploy_frontend.ps1
```

**Linux/Mac:**
```bash
chmod +x deploy_frontend.sh
./deploy_frontend.sh
```

This script will:
1. Install frontend dependencies
2. Build the React app
3. Deploy to Google App Engine

### Manual Deployment

```bash
# Build frontend
cd frontend
npm install
npm run build
cd ..

# Deploy to GAE
gcloud app deploy app.yaml
```

## Features

### 🎯 Agent Flow Visualization
- Interactive diagram showing agent architecture
- Real-time agent status
- Capability information for each agent
- Recent activity tracking

### 💬 Agent Chat Interface
- Natural language interaction with AI agents
- Powered by Google ADK + Gemini 2.0 Flash
- Context-aware responses
- Multi-turn conversations

### 🚨 Incident Management
- Automatic incident detection
- Prioritization based on severity
- Remediation workflow
- Timeline tracking

### 🛡️ Risk Budget Management
- Policy-driven autonomous operations
- Trust-based multipliers
- Budget distribution by agent
- Transaction history

### 📊 Real-Time Monitoring
- System health metrics
- Performance trends
- Service status
- Top resource-consuming queries

### ✨ Real-Time Animations & Visualizations

The platform features rich, real-time animations and colorful designs:

#### Live Dashboard Features
- **Animated Metric Cards**: Scale animations on value changes with trend indicators
- **Toast Notifications**: Real-time alerts for critical system changes
- **Live Activity Stream**: Smoothly animated activity feed with slide-in effects
- **Parameter Change Visualizer**: 3D rotation effects and confetti celebrations for VM parameter changes
- **Progress Bars**: Animated threshold-based progress indicators

#### Agent Flow Enhancements
- **Animated Edges**: Blue glow travels along connections showing data flow
- **Pulsing Nodes**: Status indicators with continuous pulse effects
- **Gradient Backgrounds**: Animated color gradients on agent nodes
- **Smooth Transitions**: AnimatePresence for panel slides and fades
- **Hover Effects**: Scale transformations and glowing borders

#### Monitoring Enhancements
- **Real-Time Updates**: Metrics update every 2-5 seconds with smooth transitions
- **Live Badge**: Pulsing indicator showing active monitoring
- **Gradient Charts**: Enhanced Recharts visualizations with custom gradients
- **Change Detection**: Automatic trend tracking with up/down indicators
- **Critical Alerts**: Toast notifications for threshold violations

#### Technical Implementation
- **Framer Motion**: Professional-grade React animation library
- **React Hot Toast**: Beautiful toast notification system
- **React Confetti**: Celebration effects for successful operations
- **Custom Hooks**: `useRealtimeMetrics`, `useActivityStream` for live data
- **WebSocket Ready**: Architecture prepared for WebSocket integration

## API Endpoints

### Incidents
- `POST /api/v1/incidents` - Create incident
- `GET /api/v1/incidents` - List all incidents
- `GET /api/v1/incidents/{id}` - Get incident details
- `GET /api/v1/incidents/{id}/timeline` - Get incident timeline

### Remediations
- `POST /api/v1/incidents/{id}/remediation` - Propose remediation
- `POST /api/v1/remediations/{id}/approve` - Approve action
- `POST /api/v1/remediations/{id}/execute` - Execute action
- `POST /api/v1/remediations/{id}/rollback` - Rollback action

### Risk Budget
- `GET /api/v1/risk-budgets/{system_id}` - Get budget status
- `GET /api/v1/risk-budgets/{system_id}/transactions` - Get transactions

### Agent Chat
- `POST /api/v1/agent/chat` - Send message to agent
- `GET /api/v1/agent/conversation/{id}` - Get conversation history

### System
- `GET /api/v1/health` - System health check
- `GET /api/v1/agents` - List all agents

### Real-Time Metrics
- `GET /api/v1/metrics/realtime` - Get real-time system metrics
- `GET /api/v1/metrics/history` - Get historical metrics data
- `GET /api/v1/activities/recent` - Get recent system activities

## Technology Stack

### Backend
- FastAPI - Modern Python web framework
- Google ADK - Agent Development Kit
- Gemini 2.0 Flash - LLM
- hdbcli - SAP HANA client
- Paramiko - SSH client

### Frontend
- React 18 - UI framework
- Vite - Build tool
- React Router - Routing
- React Flow - Agent visualization
- Recharts - Charts and graphs
- Tailwind CSS - Styling
- Axios - HTTP client
- **Framer Motion** - Animation library
- **React Hot Toast** - Toast notifications
- **React Confetti** - Celebration effects
- Lucide React - Icon library

### Deployment
- Google App Engine - Hosting
- Google Cloud - Infrastructure
- Gunicorn + Uvicorn - WSGI/ASGI server

## Project Structure

```
hana_sentinel/
├── frontend/              # React frontend application
│   ├── src/
│   │   ├── components/   # UI components
│   │   ├── pages/        # Page components
│   │   ├── services/     # API integration
│   │   └── App.jsx       # Main app
│   ├── package.json
│   └── vite.config.js
├── adk_app/              # Backend application
│   ├── agents/           # Agent implementations
│   ├── tools/            # Tool implementations  
│   ├── api.py           # FastAPI routes
│   ├── models.py        # Data models
│   └── agent.py         # ADK agent
├── config/              # Configuration
├── app.yaml            # GAE configuration
├── requirements.txt    # Python dependencies
├── main.py            # Entry point
├── dev.ps1            # Dev script (Windows)
├── dev.sh             # Dev script (Linux/Mac)
├── deploy_frontend.ps1 # Deploy script (Windows)
└── deploy_frontend.sh  # Deploy script (Linux/Mac)
```

## Configuration

### Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `GOOGLE_CLOUD_PROJECT` - GCP project ID
- `HANA_HOST`, `HANA_PORT`, `HANA_USER`, `HANA_PASSWORD` - HANA connection
- `SSH_HOST`, `SSH_USER` - SSH access for OS-level operations
- `ADK_MODEL` - Gemini model to use (default: gemini-2.0-flash)

### Risk Scores

Configure risk scores for different operations in `app.yaml`:
- Low risk (1-5): Monitoring, reading
- Medium risk (6-11): Configuration changes, backups
- High risk (12-20): Service restarts, data modifications
- Critical risk (20+): Failover, major changes

## Development

### Running Tests

```bash
python main.py verify
```

### Chaos Engineering

```bash
python main.py chaos
```

### API Documentation

When running locally, visit `http://localhost:8000/docs` for interactive API documentation.

## Security

- All API endpoints require authentication in production
- Risk budget system prevents unauthorized operations
- Policy engine enforces governance rules
- Action certificates provide audit trail
- Human-in-the-loop for high-risk operations

## Monitoring

The system provides multiple monitoring interfaces:
- Web UI dashboard
- Real-time metrics API
- System health endpoint
- Agent activity logs

## Support

For issues and questions:
- Check the API documentation at `/docs`
- Review the frontend README in `frontend/README.md`
- Examine log files for errors

## License

Proprietary - Internal Use Only

---

Built with ❤️ for autonomous SAP HANA operations
