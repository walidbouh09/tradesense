#!/bin/bash
# TradeSense AI - Quick Start Script for Linux/macOS
# This script starts both backend and frontend for immediate testing

set -e  # Exit on any error

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
print_colored $CYAN "    🚀 Professional Prop Trading Platform - Quick Start"
echo

print_header "Checking Prerequisites"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed or not in PATH"
    echo "Please install Python 3.8+ from https://python.org"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    print_error "Python 3.8+ required, found $PYTHON_VERSION"
    exit 1
fi

print_success "Python $PYTHON_VERSION is compatible"

# Check if Node.js is installed (optional for backend-only mode)
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    print_success "Node.js $NODE_VERSION is installed"
    HAS_NODE=true
else
    print_warning "Node.js not found. Frontend will be skipped."
    HAS_NODE=false
fi

print_header "Setting Up Environment"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    print_step "Creating Python virtual environment..."
    python3 -m venv .venv
    print_success "Virtual environment created"
else
    print_success "Virtual environment already exists"
fi

# Activate virtual environment
print_step "Activating virtual environment..."
source .venv/bin/activate

# Install Python dependencies
if [ ! -f ".venv/installed" ]; then
    print_step "Installing Python dependencies..."
    pip install --upgrade pip --quiet
    pip install Flask==3.0.0 Flask-CORS==4.0.0 Flask-SocketIO==5.3.6 \
        Flask-JWT-Extended==4.6.0 Flask-SQLAlchemy==3.1.1 \
        python-dotenv==1.0.0 marshmallow==3.20.1 redis==5.0.1 \
        eventlet==0.33.3 --quiet

    if [ $? -eq 0 ]; then
        touch .venv/installed
        print_success "Python dependencies installed"
    else
        print_error "Failed to install Python dependencies"
        exit 1
    fi
else
    print_success "Python dependencies already installed"
fi

# Create basic .env file if it doesn't exist
if [ ! -f ".env" ]; then
    print_step "Creating basic configuration file..."
    cat > .env << EOF
# TradeSense AI - Basic Configuration
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=dev-secret-key-for-demo-only
JWT_SECRET_KEY=jwt-secret-key-for-demo-only
DATABASE_URL=sqlite:///tradesense_demo.db
REDIS_URL=redis://localhost:6379/0
CORS_ORIGINS=http://localhost:3000,http://localhost:3001,http://localhost:5173
LOG_LEVEL=INFO
YAHOO_FINANCE_ENABLED=True
MARKET_DATA_CACHE_TTL=60
EOF
    print_success "Configuration file created"
else
    print_success "Configuration file exists"
fi

# Create logs directory
mkdir -p logs

# Install frontend dependencies if Node.js is available
if [ "$HAS_NODE" = true ] && [ -d "frontend" ]; then
    print_step "Setting up frontend..."
    cd frontend
    if [ ! -d "node_modules" ]; then
        print_step "Installing frontend dependencies..."
        npm install --silent
        if [ $? -eq 0 ]; then
            print_success "Frontend dependencies installed"
        else
            print_error "Failed to install frontend dependencies"
            cd ..
            exit 1
        fi
    else
        print_success "Frontend dependencies already installed"
    fi
    cd ..
elif [ ! -d "frontend" ]; then
    print_warning "Frontend directory not found, skipping frontend setup"
fi

print_header "Starting Services"

echo
print_colored $GREEN "🎉 Setup completed successfully!"
echo
print_colored $CYAN "📋 Demo Credentials:"
print_colored $CYAN "   - Demo Trader: demo@tradesense.ai / demo123456"
print_colored $CYAN "   - Admin User: admin@tradesense.ai / admin123456"
echo
print_colored $BLUE "🚀 Starting TradeSense AI..."
echo

# Function to cleanup background processes
cleanup() {
    print_colored $YELLOW "🛑 Shutting down services..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
    fi
    echo "👋 Services stopped. Goodbye!"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start backend
print_step "Starting backend server..."
source .venv/bin/activate
python run.py &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Check if backend started successfully
if ps -p $BACKEND_PID > /dev/null; then
    print_success "Backend server started (PID: $BACKEND_PID)"
else
    print_error "Failed to start backend server"
    exit 1
fi

# Start frontend if available
if [ "$HAS_NODE" = true ] && [ -d "frontend" ]; then
    print_step "Starting frontend server..."
    cd frontend
    npm start &
    FRONTEND_PID=$!
    cd ..

    sleep 2

    if ps -p $FRONTEND_PID > /dev/null; then
        print_success "Frontend server started (PID: $FRONTEND_PID)"
    else
        print_warning "Frontend server failed to start"
        unset FRONTEND_PID
    fi
fi

echo
print_colored $GREEN "✅ TradeSense AI is running!"
echo
print_colored $CYAN "🌐 Access URLs:"
print_colored $CYAN "   - Backend API: http://localhost:5000"
if [ ! -z "$FRONTEND_PID" ]; then
    print_colored $CYAN "   - Frontend App: http://localhost:3000"
fi
print_colored $CYAN "   - API Docs: http://localhost:5000/docs"
print_colored $CYAN "   - Health Check: http://localhost:5000/health"
echo
print_colored $YELLOW "💡 Tips:"
print_colored $YELLOW "   - Press Ctrl+C to stop all services"
print_colored $YELLOW "   - Check logs in the 'logs' directory"
print_colored $YELLOW "   - Edit .env file to customize configuration"
echo
print_colored $BLUE "📖 For more information, see README.md"
print_colored $BLUE "🆘 For support, visit: https://github.com/your-repo/tradesense/issues"
echo

# Open browser if frontend is running
if [ ! -z "$FRONTEND_PID" ]; then
    sleep 5
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:3000 &>/dev/null &
    elif command -v open &> /dev/null; then
        open http://localhost:3000 &>/dev/null &
    fi
fi

# Keep the script running and wait for interrupt
print_colored $GREEN "🎯 Services are running. Press Ctrl+C to stop."
echo

# Wait for interrupt
while true; do
    sleep 1
done
