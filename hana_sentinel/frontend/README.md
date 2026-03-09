# HANA Sentinel Frontend

React-based web interface for the HANA Sentinel AI Operations Platform.

## Features

- 🎯 **Agent Flow Visualization** - Interactive diagram showing agent architecture
- 💬 **Agent Chat Interface** - Chat with AI agents powered by Google ADK
- 🚨 **Incident Management** - Track and manage system incidents
- 🛡️ **Risk Budget Dashboard** - Monitor autonomous operation budgets
- 📊 **Real-time Monitoring** - System metrics and performance tracking

## Development

### Prerequisites

- Node.js 18+ and npm
- Python 3.11+
- Google Cloud SDK (for deployment)

### Local Development

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Start development server:
```bash
npm run dev
```

The app will be available at `http://localhost:3000`

The development server proxies API requests to `http://localhost:8000`

### Running the Backend

In a separate terminal:

```bash
cd ..
python main.py api
```

This starts the FastAPI backend on port 8000.

## Building for Production

```bash
npm run build
```

Built files will be in the `dist/` directory.

## Deployment to Google App Engine

From the project root:

### Windows:
```powershell
.\deploy_frontend.ps1
```

### Linux/Mac:
```bash
chmod +x deploy_frontend.sh
./deploy_frontend.sh
```

This will:
1. Install frontend dependencies
2. Build the React app
3. Deploy to Google App Engine

## Project Structure

```
frontend/
├── src/
│   ├── components/      # Reusable UI components
│   │   ├── Layout.jsx
│   │   └── AgentNode.jsx
│   ├── pages/          # Page components
│   │   ├── Dashboard.jsx
│   │   ├── AgentFlow.jsx
│   │   ├── AgentChat.jsx
│   │   ├── Incidents.jsx
│   │   ├── RiskBudget.jsx
│   │   └── Monitoring.jsx
│   ├── services/       # API integration
│   │   └── api.js
│   ├── App.jsx         # Main app component
│   ├── main.jsx        # Entry point
│   └── index.css       # Global styles
├── public/             # Static assets
├── index.html          # HTML template
├── package.json        # Dependencies
├── vite.config.js      # Vite configuration
└── tailwind.config.js  # Tailwind CSS configuration
```

## Technology Stack

- **React 18** - UI framework
- **Vite** - Build tool and dev server
- **React Router** - Client-side routing
- **React Flow** - Agent flow visualization
- **Recharts** - Data visualization
- **Tailwind CSS** - Styling
- **Lucide React** - Icons
- **Axios** - HTTP client

## Environment Variables

Create a `.env` file in the frontend directory:

```env
VITE_API_URL=http://localhost:8000/api/v1
```

For production, the API URL is automatically set to `/api/v1` (same origin).

## API Integration

The frontend communicates with the FastAPI backend through the API service (`src/services/api.js`).

Available API endpoints:
- `/api/v1/incidents` - Incident management
- `/api/v1/remediations` - Remediation actions
- `/api/v1/risk-budgets` - Risk budget tracking
- `/api/v1/agent/chat` - Agent chat interface
- `/api/v1/health` - System health status

## License

Proprietary
