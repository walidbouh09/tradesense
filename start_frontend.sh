#!/bin/bash
# TradeSense AI - Frontend Startup Script
# Simple script to start the React frontend reliably

set -e

echo "🚀 Starting TradeSense AI Frontend..."

# Navigate to frontend directory
cd "$(dirname "$0")/frontend"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Kill any existing processes on port 3001
echo "🧹 Cleaning up existing processes..."
lsof -ti:3001 | xargs kill -9 2>/dev/null || true

# Start the React development server
echo "🎨 Starting React development server on port 3001..."
PORT=3001 npm start

echo "✅ Frontend should be available at http://localhost:3001"
