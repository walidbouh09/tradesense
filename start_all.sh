#!/bin/bash
# TradeSense AI - Complete Startup Script
# Starts both backend and frontend services with proper monitoring

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Print colored output
print_colored() {
    echo -e "${1}${2}${NC}"
}

print_header() {
    echo
    print_colored $PURPLE "============================================================"
    print_colored $PURPLE " $1"
    print_colored $PURPLE "============================================================"
    echo
}

print_step() {
    print_colored $BLUE "📋 $1"
}

print_success() {
    print_colored $GREEN "✅ $1"
}

print_warning() {
    print_colored $YELLOW "⚠️  $1"
}

print_error() {
    print_colored $RED "❌ $1"
}

# Print banner
echo
print_colored $PURPLE " ████████╗██████╗  █████╗ ██████╗ ███████╗███████╗███████╗███╗   ██╗███████╗███████╗"
print_colored $PURPLE " ╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔════╝██╔════╝████╗  ██║██╔════╝██╔════╝"
print_colored $PURPLE "    ██║   ██████╔╝███████║██║  ██║█████╗  ███████╗█████╗  ██╔██╗ ██║███████╗█████╗  "
print_colored $PURPLE "    ██║   ██╔══██╗██╔══██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██║╚██╗██║╚════██║██╔══╝  "
print_colored $PURPLE "    ██║   ██║  ██║██║  ██║██████╔╝███████╗███████║███████╗██║ ╚████║███████║███████╗"
print_colored $PURPLE "    ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝"
echo
print_colored $CYAN "    🚀 Professional Prop Trading Platform - Complete Startup"
echo

# Cleanup function
cleanup() {
    print_colored $YELLOW "🛑 Shutting down TradeSense AI services..."

    if [ ! -z "$BACKEND_PID" ] && ps -p $BACKEND_PID > /dev/null; then
        print_step "Stopping backend server (PID: $BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null || true
        wait $BACKEND_PID 2>/dev/null || true
        print_success "Backend stopped"
    fi

    if [ ! -z "$FRONTEND_PID" ] && ps -p $FRONTEND_PID > /dev/null; then
        print_step "Stopping frontend server (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID 2>/dev/null || true
        wait $FRONTEND_PID 2>/dev/null || true
        print_success "Frontend stopped"
    fi

    # Kill any remaining processes on our ports
    lsof -ti:5000 | xargs kill -9 2>/dev/null || true
    lsof -ti:3001 | xargs kill -9 2>/dev/null || true

    echo
    print_colored $GREEN "👋 TradeSense AI services stopped. Goodbye!"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

print_header "Checking Prerequisites"

# Check Python
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    print_error "Python is not installed or not in PATH"
    exit 1
fi

PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

print_success "$PYTHON_CMD is available"

# Check Node.js (optional)
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    print_success "Node.js $NODE_VERSION is available"
    HAS_NODE=true
else
    print_warning "Node.js not found. Only backend will be started."
    HAS_NODE=false
fi

print_header "Starting Backend Service"

# Check if backend files exist
if [ ! -f "app_simple.py" ]; then
    print_error "Backend file 'app_simple.py' not found"
    exit 1
fi

# Start backend
print_step "Starting Flask backend server..."
$PYTHON_CMD app_simple.py > backend.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to start
print_step "Waiting for backend to initialize..."
sleep 3

# Check if backend is running
if ps -p $BACKEND_PID > /dev/null; then
    # Test backend health
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        print_success "Backend server started successfully (PID: $BACKEND_PID)"
        print_success "Backend URL: http://localhost:5000"
    else
        print_warning "Backend started but health check failed"
        print_step "Waiting 5 more seconds..."
        sleep 5
        if curl -s http://localhost:5000/health > /dev/null 2>&1; then
            print_success "Backend is now healthy"
        else
            print_error "Backend health check still failing"
        fi
    fi
else
    print_error "Backend failed to start"
    print_error "Check backend.log for details"
    exit 1
fi

# Start frontend if Node.js is available
if [ "$HAS_NODE" = true ] && [ -d "frontend" ]; then
    print_header "Starting Frontend Service"

    # Navigate to frontend directory
    cd frontend

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        print_step "Installing frontend dependencies..."
        npm install --silent > ../frontend_install.log 2>&1 || {
            print_error "Failed to install frontend dependencies"
            print_error "Check frontend_install.log for details"
            cd ..
            cleanup
        }
        print_success "Frontend dependencies installed"
    fi

    # Start frontend
    print_step "Starting React frontend server..."
    PORT=3001 npm start > ../frontend.log 2>&1 &
    FRONTEND_PID=$!

    cd ..

    # Wait for frontend to start
    print_step "Waiting for frontend to initialize..."
    sleep 8

    # Check if frontend is running
    if ps -p $FRONTEND_PID > /dev/null; then
        print_success "Frontend server started successfully (PID: $FRONTEND_PID)"
        print_success "Frontend URL: http://localhost:3001"
    else
        print_warning "Frontend failed to start, but backend is still running"
        print_warning "You can use the test interface instead"
        FRONTEND_PID=""
    fi
fi

print_header "🎉 TradeSense AI Startup Complete!"

echo
print_colored $GREEN "🌐 Service URLs:"
print_colored $CYAN "   - Backend API: http://localhost:5000"
print_colored $CYAN "   - API Health: http://localhost:5000/health"
print_colored $CYAN "   - API Info: http://localhost:5000/api"

if [ ! -z "$FRONTEND_PID" ] && ps -p $FRONTEND_PID > /dev/null; then
    print_colored $CYAN "   - Frontend App: http://localhost:3001"
fi

# Always available
print_colored $CYAN "   - Test Interface: file://$(pwd)/test_frontend.html"

echo
print_colored $YELLOW "🔑 Demo Credentials:"
print_colored $YELLOW "   - Demo Trader: demo.trader@tradesense.ai / demo123456"
print_colored $YELLOW "   - Admin User: admin@tradesense.ai / admin123456"

echo
print_colored $BLUE "💡 Tips:"
print_colored $BLUE "   - Press Ctrl+C to stop all services"
print_colored $BLUE "   - Check backend.log for backend logs"
if [ "$HAS_NODE" = true ]; then
    print_colored $BLUE "   - Check frontend.log for frontend logs"
fi
print_colored $BLUE "   - Use test_frontend.html for immediate testing"

echo
print_colored $GREEN "📊 System Status:"
print_colored $GREEN "   - Backend: ✅ Running (PID: $BACKEND_PID)"
if [ ! -z "$FRONTEND_PID" ] && ps -p $FRONTEND_PID > /dev/null; then
    print_colored $GREEN "   - Frontend: ✅ Running (PID: $FRONTEND_PID)"
else
    print_colored $YELLOW "   - Frontend: ⚠️  Not running (use test interface)"
fi

echo
print_colored $PURPLE "🎯 TradeSense AI is ready for trading!"
echo

# Open browser automatically
if [ ! -z "$FRONTEND_PID" ] && ps -p $FRONTEND_PID > /dev/null; then
    print_step "Opening frontend in browser..."
    sleep 3
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:3001 &>/dev/null &
    elif command -v open &> /dev/null; then
        open http://localhost:3001 &>/dev/null &
    fi
else
    print_step "Opening test interface in browser..."
    if command -v xdg-open &> /dev/null; then
        xdg-open "file://$(pwd)/test_frontend.html" &>/dev/null &
    elif command -v open &> /dev/null; then
        open "file://$(pwd)/test_frontend.html" &>/dev/null &
    fi
fi

# Keep services running
print_colored $GREEN "🔄 Services are running. Press Ctrl+C to stop all services."
echo

# Monitor services
while true; do
    sleep 10

    # Check if backend is still running
    if ! ps -p $BACKEND_PID > /dev/null; then
        print_error "Backend process died unexpectedly"
        cleanup
    fi

    # Check if frontend is still running (if it was started)
    if [ ! -z "$FRONTEND_PID" ] && ! ps -p $FRONTEND_PID > /dev/null; then
        print_warning "Frontend process died"
        FRONTEND_PID=""
    fi
done
