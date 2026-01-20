#!/bin/bash

# TradeSense Pro - Professional Setup Script
# This script sets up a complete development environment for TradeSense Pro

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="TradeSense Pro"
PROJECT_DIR="$(pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$PROJECT_DIR/venv"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}\n"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check system requirements
check_system_requirements() {
    print_header "Checking System Requirements"

    # Check operating system
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="Linux"
        print_status "Operating System: Linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macOS"
        print_status "Operating System: macOS"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        OS="Windows"
        print_status "Operating System: Windows (Git Bash/WSL)"
    else
        print_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi

    # Check Python version
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version | cut -d ' ' -f 2)
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d '.' -f 1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d '.' -f 2)

        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
            print_success "Python $PYTHON_VERSION found"
        else
            print_error "Python 3.8+ required, found $PYTHON_VERSION"
            exit 1
        fi
    else
        print_error "Python 3.8+ is required but not installed"
        print_status "Please install Python 3.8+ from https://python.org"
        exit 1
    fi

    # Check Node.js version
    if command_exists node; then
        NODE_VERSION=$(node --version | sed 's/v//')
        NODE_MAJOR=$(echo $NODE_VERSION | cut -d '.' -f 1)

        if [ "$NODE_MAJOR" -ge 18 ]; then
            print_success "Node.js $NODE_VERSION found"
        else
            print_error "Node.js 18+ required, found $NODE_VERSION"
            exit 1
        fi
    else
        print_error "Node.js 18+ is required but not installed"
        print_status "Please install Node.js from https://nodejs.org"
        exit 1
    fi

    # Check npm version
    if command_exists npm; then
        NPM_VERSION=$(npm --version)
        print_success "npm $NPM_VERSION found"
    else
        print_error "npm is required but not installed"
        exit 1
    fi

    # Check Docker
    if command_exists docker; then
        DOCKER_VERSION=$(docker --version | cut -d ' ' -f 3 | sed 's/,//')
        print_success "Docker $DOCKER_VERSION found"

        # Check if Docker daemon is running
        if docker info >/dev/null 2>&1; then
            print_success "Docker daemon is running"
        else
            print_warning "Docker daemon is not running. Please start Docker."
        fi
    else
        print_warning "Docker not found. Install Docker for full development experience."
    fi

    # Check Docker Compose
    if command_exists docker-compose; then
        COMPOSE_VERSION=$(docker-compose --version | cut -d ' ' -f 3 | sed 's/,//')
        print_success "Docker Compose $COMPOSE_VERSION found"
    elif docker compose version >/dev/null 2>&1; then
        COMPOSE_VERSION=$(docker compose version | cut -d ' ' -f 4)
        print_success "Docker Compose $COMPOSE_VERSION found (plugin)"
    else
        print_warning "Docker Compose not found. Install for container orchestration."
    fi

    # Check Git
    if command_exists git; then
        GIT_VERSION=$(git --version | cut -d ' ' -f 3)
        print_success "Git $GIT_VERSION found"
    else
        print_error "Git is required but not installed"
        exit 1
    fi
}

# Function to create directory structure
create_directory_structure() {
    print_header "Creating Directory Structure"

    # Create main directories
    mkdir -p backend/app/{core,api/v1,models,schemas,services,workers,utils,tests}
    mkdir -p backend/alembic/versions
    mkdir -p backend/requirements
    mkdir -p frontend/src/{app,components/{ui,layout,forms,charts,trading},lib,hooks,store,types,styles}
    mkdir -p frontend/public/{images,icons}
    mkdir -p frontend/__tests__/{components,pages,utils}
    mkdir -p shared/{types,constants}
    mkdir -p infrastructure/{docker,k8s,terraform,nginx,prometheus,grafana}
    mkdir -p docs/{api,deployment,development,architecture}
    mkdir -p scripts
    mkdir -p .github/workflows
    mkdir -p logs
    mkdir -p uploads

    print_success "Directory structure created"
}

# Function to setup Python virtual environment
setup_python_environment() {
    print_header "Setting up Python Virtual Environment"

    cd "$BACKEND_DIR"

    # Create virtual environment
    if [ ! -d "$VENV_DIR" ]; then
        print_status "Creating Python virtual environment..."
        python3 -m venv "$VENV_DIR"
        print_success "Virtual environment created at $VENV_DIR"
    else
        print_warning "Virtual environment already exists"
    fi

    # Activate virtual environment
    print_status "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"

    # Upgrade pip
    print_status "Upgrading pip..."
    pip install --upgrade pip

    # Install requirements if they exist
    if [ -f "requirements.txt" ]; then
        print_status "Installing Python dependencies..."
        pip install -r requirements.txt
        print_success "Python dependencies installed"
    else
        print_warning "requirements.txt not found, skipping dependency installation"
    fi

    cd "$PROJECT_DIR"
}

# Function to setup Node.js environment
setup_node_environment() {
    print_header "Setting up Node.js Environment"

    cd "$FRONTEND_DIR"

    # Install dependencies if package.json exists
    if [ -f "package.json" ]; then
        print_status "Installing Node.js dependencies..."
        npm install
        print_success "Node.js dependencies installed"
    else
        print_warning "package.json not found, skipping dependency installation"
    fi

    cd "$PROJECT_DIR"
}

# Function to setup database
setup_database() {
    print_header "Setting up Database"

    # Check if PostgreSQL is running via Docker
    if command_exists docker && docker info >/dev/null 2>&1; then
        print_status "Starting PostgreSQL with Docker..."

        # Check if container already exists
        if docker ps -a --format "table {{.Names}}" | grep -q "tradesense-postgres"; then
            print_status "PostgreSQL container exists, starting..."
            docker start tradesense-postgres >/dev/null 2>&1 || true
        else
            print_status "Creating PostgreSQL container..."
            docker run -d \
                --name tradesense-postgres \
                -e POSTGRES_DB=tradesense_pro \
                -e POSTGRES_USER=tradesense \
                -e POSTGRES_PASSWORD=tradesense_password \
                -p 5432:5432 \
                -v tradesense_postgres_data:/var/lib/postgresql/data \
                postgres:15-alpine
        fi

        print_success "PostgreSQL container started"
        print_status "Database URL: postgresql://tradesense:tradesense_password@localhost:5432/tradesense_pro"
    else
        print_warning "Docker not available. Please install PostgreSQL manually."
        print_status "Required database: tradesense_pro"
        print_status "Recommended user: tradesense / tradesense_password"
    fi
}

# Function to setup Redis
setup_redis() {
    print_header "Setting up Redis"

    # Check if Redis is running via Docker
    if command_exists docker && docker info >/dev/null 2>&1; then
        print_status "Starting Redis with Docker..."

        # Check if container already exists
        if docker ps -a --format "table {{.Names}}" | grep -q "tradesense-redis"; then
            print_status "Redis container exists, starting..."
            docker start tradesense-redis >/dev/null 2>&1 || true
        else
            print_status "Creating Redis container..."
            docker run -d \
                --name tradesense-redis \
                -p 6379:6379 \
                -v tradesense_redis_data:/data \
                redis:7-alpine redis-server --appendonly yes
        fi

        print_success "Redis container started"
        print_status "Redis URL: redis://localhost:6379/0"
    else
        print_warning "Docker not available. Please install Redis manually."
    fi
}

# Function to create environment files
create_environment_files() {
    print_header "Creating Environment Files"

    # Backend .env file
    if [ ! -f "$BACKEND_DIR/.env" ]; then
        print_status "Creating backend .env file..."
        cat > "$BACKEND_DIR/.env" << EOF
# TradeSense Pro - Backend Environment Variables

# Environment
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=dev-secret-key-change-in-production

# Database
DATABASE_URL=postgresql+asyncpg://tradesense:tradesense_password@localhost:5432/tradesense_pro
POSTGRES_SERVER=localhost
POSTGRES_USER=tradesense
POSTGRES_PASSWORD=tradesense_password
POSTGRES_DB=tradesense_pro
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# CORS
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# JWT
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# Email (Development)
EMAILS_ENABLED=false
SMTP_HOST=localhost
SMTP_PORT=1025
EMAILS_FROM_EMAIL=noreply@tradesense.ma

# Market Data
ALPHA_VANTAGE_API_KEY=demo

# Payment (Development)
PAYMENT_PROVIDER=mock
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here

# Monitoring
LOG_LEVEL=DEBUG
SENTRY_DSN=

# Features
FEATURE_ADVANCED_ANALYTICS=true
EOF
        print_success "Backend .env file created"
    else
        print_warning "Backend .env file already exists"
    fi

    # Frontend .env.local file
    if [ ! -f "$FRONTEND_DIR/.env.local" ]; then
        print_status "Creating frontend .env.local file..."
        cat > "$FRONTEND_DIR/.env.local" << EOF
# TradeSense Pro - Frontend Environment Variables

# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws

# Application
NEXT_PUBLIC_APP_NAME="TradeSense Pro"
NEXT_PUBLIC_APP_VERSION="1.0.0"
NEXT_PUBLIC_ENVIRONMENT=development

# Features
NEXT_PUBLIC_FEATURE_ADVANCED_ANALYTICS=true
NEXT_PUBLIC_FEATURE_SOCIAL_TRADING=false

# External Services
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here
NEXT_PUBLIC_GOOGLE_ANALYTICS_ID=
EOF
        print_success "Frontend .env.local file created"
    else
        print_warning "Frontend .env.local file already exists"
    fi
}

# Function to run database migrations
run_database_migrations() {
    print_header "Running Database Migrations"

    cd "$BACKEND_DIR"

    # Check if virtual environment exists and activate it
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
    fi

    # Check if Alembic is configured
    if [ -f "alembic.ini" ]; then
        print_status "Running Alembic migrations..."
        alembic upgrade head
        print_success "Database migrations completed"
    else
        print_warning "Alembic not configured. Database migrations skipped."
    fi

    cd "$PROJECT_DIR"
}

# Function to setup git hooks
setup_git_hooks() {
    print_header "Setting up Git Hooks"

    # Initialize git repository if not already initialized
    if [ ! -d ".git" ]; then
        print_status "Initializing Git repository..."
        git init
        print_success "Git repository initialized"
    fi

    # Setup pre-commit hooks if available
    if command_exists pre-commit; then
        print_status "Installing pre-commit hooks..."
        pre-commit install
        print_success "Pre-commit hooks installed"
    else
        print_warning "pre-commit not found. Install with: pip install pre-commit"
    fi
}

# Function to create useful scripts
create_scripts() {
    print_header "Creating Development Scripts"

    # Development start script
    cat > scripts/start-dev.sh << 'EOF'
#!/bin/bash
# Start development environment

echo "Starting TradeSense Pro Development Environment..."

# Start services with Docker Compose
if command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d postgres redis
    echo "Database and Redis started"

    # Wait for services to be ready
    sleep 5

    # Start backend in background
    cd backend
    source ../venv/bin/activate
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!
    cd ..

    # Start frontend in background
    cd frontend
    npm run dev &
    FRONTEND_PID=$!
    cd ..

    echo "Development servers started:"
    echo "- Backend: http://localhost:8000"
    echo "- Frontend: http://localhost:3000"
    echo "- API Docs: http://localhost:8000/docs"
    echo ""
    echo "Press Ctrl+C to stop all services"

    # Wait for interrupt
    trap 'kill $BACKEND_PID $FRONTEND_PID; docker-compose stop postgres redis' INT
    wait
else
    echo "Docker Compose not found. Please start services manually."
fi
EOF

    # Production build script
    cat > scripts/build-prod.sh << 'EOF'
#!/bin/bash
# Build production images

echo "Building production images for TradeSense Pro..."

# Build backend image
docker build -t tradesense-pro-backend:latest ./backend

# Build frontend image
docker build -t tradesense-pro-frontend:latest ./frontend

echo "Production images built successfully"
EOF

    # Database backup script
    cat > scripts/backup-db.sh << 'EOF'
#!/bin/bash
# Backup database

BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="tradesense_backup_$TIMESTAMP.sql"

mkdir -p $BACKUP_DIR

echo "Creating database backup..."
docker exec tradesense-postgres pg_dump -U tradesense tradesense_pro > "$BACKUP_DIR/$BACKUP_FILE"

echo "Database backup created: $BACKUP_DIR/$BACKUP_FILE"
EOF

    # Make scripts executable
    chmod +x scripts/*.sh

    print_success "Development scripts created"
}

# Function to display final instructions
display_final_instructions() {
    print_header "Setup Complete!"

    echo -e "${GREEN}TradeSense Pro development environment has been set up successfully!${NC}\n"

    echo -e "${BLUE}Getting Started:${NC}"
    echo "1. Activate Python virtual environment:"
    echo -e "   ${YELLOW}source venv/bin/activate${NC}"
    echo ""
    echo "2. Start development servers:"
    echo -e "   ${YELLOW}./scripts/start-dev.sh${NC}"
    echo ""
    echo "3. Or start services individually:"
    echo -e "   Backend:  ${YELLOW}cd backend && uvicorn app.main:app --reload${NC}"
    echo -e "   Frontend: ${YELLOW}cd frontend && npm run dev${NC}"
    echo ""

    echo -e "${BLUE}Access Points:${NC}"
    echo -e "• Frontend:     ${YELLOW}http://localhost:3000${NC}"
    echo -e "• Backend API:  ${YELLOW}http://localhost:8000${NC}"
    echo -e "• API Docs:     ${YELLOW}http://localhost:8000/docs${NC}"
    echo -e "• Database:     ${YELLOW}postgresql://tradesense:tradesense_password@localhost:5432/tradesense_pro${NC}"
    echo -e "• Redis:        ${YELLOW}redis://localhost:6379/0${NC}"
    echo ""

    echo -e "${BLUE}Admin Tools (if Docker is running):${NC}"
    echo -e "• pgAdmin:      ${YELLOW}http://localhost:5050${NC} (admin@tradesense.ma / admin123)"
    echo -e "• Redis UI:     ${YELLOW}http://localhost:8081${NC} (admin / admin123)"
    echo -e "• Monitoring:   ${YELLOW}docker-compose --profile monitoring up -d${NC}"
    echo ""

    echo -e "${BLUE}Next Steps:${NC}"
    echo "1. Review and customize environment files (.env, .env.local)"
    echo "2. Set up your IDE with Python and TypeScript support"
    echo "3. Run tests to ensure everything works"
    echo "4. Start building amazing features!"
    echo ""

    echo -e "${GREEN}Happy coding! 🚀${NC}"
}

# Main execution
main() {
    clear
    echo -e "${BLUE}"
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════════╗
║                        TradeSense Pro                           ║
║                   Professional Setup Script                     ║
║                                                                  ║
║           Setting up your development environment...            ║
╚══════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}\n"

    # Run setup steps
    check_system_requirements
    create_directory_structure
    setup_python_environment
    setup_node_environment
    setup_database
    setup_redis
    create_environment_files
    run_database_migrations
    setup_git_hooks
    create_scripts
    display_final_instructions
}

# Run main function
main "$@"
