#!/bin/bash
# Local Development Script - Run Frontend and Backend concurrently

echo "🚀 Starting HANA Sentinel Development Environment"
echo "=================================================="

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup EXIT INT TERM

# Start Backend
echo ""
echo "🐍 Starting FastAPI backend on port 8000..."
python main.py api &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start Frontend
echo ""
echo "⚛️  Starting React frontend on port 3000..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Development environment is running!"
echo ""
echo "📖 Frontend: http://localhost:3000"
echo "📖 Backend API: http://localhost:8000"
echo "📖 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for processes
wait
