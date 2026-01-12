#!/bin/bash

# Arbitrage Platform Startup Script
# Usage: ./start.sh [backend|frontend|all]

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

start_backend() {
    echo "🚀 Starting Backend..."
    cd "$PROJECT_ROOT/backend"
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        echo "📦 Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate and install dependencies
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    
    # Start the server
    echo "🔌 Backend running at http://localhost:8000"
    uvicorn main:app --reload --port 8000
}

start_frontend() {
    echo "🎨 Starting Frontend..."
    cd "$PROJECT_ROOT/frontend"
    
    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo "📦 Installing dependencies..."
        npm install
    fi
    
    # Start the development server
    echo "🌐 Frontend running at http://localhost:3000"
    npm run dev
}

case "${1:-all}" in
    backend)
        start_backend
        ;;
    frontend)
        start_frontend
        ;;
    all)
        echo "======================================"
        echo "  Arbitrage Platform Startup"
        echo "======================================"
        echo ""
        echo "Starting both services..."
        echo "- Backend:  http://localhost:8000"
        echo "- Frontend: http://localhost:3000"
        echo ""
        
        # Start backend in background
        start_backend &
        BACKEND_PID=$!
        
        # Wait a bit for backend to initialize
        sleep 3
        
        # Start frontend
        start_frontend &
        FRONTEND_PID=$!
        
        # Handle shutdown
        trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
        
        wait
        ;;
    *)
        echo "Usage: $0 [backend|frontend|all]"
        exit 1
        ;;
esac

