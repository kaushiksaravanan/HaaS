#!/bin/bash
# Build and Deploy Script for Google App Engine

set -e

echo "🏗️  HANA Sentinel - Build & Deploy to Google App Engine"
echo "=========================================================="

# Step 1: Install frontend dependencies
echo ""
echo "📦 Installing frontend dependencies..."
cd frontend
npm install

# Step 2: Build frontend
echo ""
echo "🔨 Building React frontend..."
npm run build

# Verify build
if [ ! -d "dist" ]; then
    echo "❌ Frontend build failed - dist directory not found"
    exit 1
fi

echo "✅ Frontend built successfully"
cd ..

# Step 3: Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Step 4: Deploy to Google App Engine
echo ""
echo "🚀 Deploying to Google App Engine..."
gcloud app deploy app.yaml --quiet

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Your application is now available at:"
gcloud app browse --no-launch-browser
