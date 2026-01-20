#!/bin/bash

# ============================================================================
# TradeSense AI - Docker Status Check & Fix Script
# ============================================================================
# This script checks the current Docker setup, identifies issues, and provides
# fixes for the TradeSense AI platform deployment.
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Icons
CHECK="✅"
WARNING="⚠️ "
ERROR="❌"
FIX="🔧"
INFO="ℹ️ "
ROCKET="🚀"

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}                TradeSense AI - Docker Status Check${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# ============================================================================
# STEP 1: Check Prerequisites
# ============================================================================
echo -e "${PURPLE}🔍 STEP 1: Checking Prerequisites${NC}"
echo ""

# Check Docker
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    echo -e "  ${CHECK} Docker installed: ${DOCKER_VERSION}"
else
    echo -e "  ${ERROR} Docker not found. Please install Docker first."
    exit 1
fi

# Check Docker Compose
if command -v docker-compose &> /dev/null; then
    COMPOSE_VERSION=$(docker-compose --version)
    echo -e "  ${CHECK} Docker Compose installed: ${COMPOSE_VERSION}"
else
    echo -e "  ${ERROR} Docker Compose not found. Please install Docker Compose first."
    exit 1
fi

# Check Docker daemon
if docker info &> /dev/null; then
    echo -e "  ${CHECK} Docker daemon is running"
else
    echo -e "  ${ERROR} Docker daemon is not running. Please start Docker."
    exit 1
fi

echo ""

# ============================================================================
# STEP 2: Analyze Current Configuration
# ============================================================================
echo -e "${PURPLE}🔍 STEP 2: Analyzing Current Configuration${NC}"
echo ""

# Check docker-compose.yml
if [ -f "docker-compose.yml" ]; then
    echo -e "  ${CHECK} docker-compose.yml found"

    # Validate compose file
    if docker-compose config > /dev/null 2>&1; then
        echo -e "  ${CHECK} docker-compose.yml is valid"
    else
        echo -e "  ${WARNING}docker-compose.yml has validation issues"
        echo -e "      Run: docker-compose config to see details"
    fi
else
    echo -e "  ${ERROR} docker-compose.yml not found"
fi

# Check Dockerfiles
echo ""
echo -e "  ${INFO}Checking Dockerfiles:"
if [ -f "Dockerfile.backend" ]; then
    echo -e "    ${CHECK} Dockerfile.backend found"
else
    echo -e "    ${WARNING}Dockerfile.backend not found"
fi

if [ -f "Dockerfile.frontend" ]; then
    echo -e "    ${CHECK} Dockerfile.frontend found"
else
    echo -e "    ${WARNING}Dockerfile.frontend not found"
fi

if [ -f "backend/Dockerfile" ]; then
    echo -e "    ${CHECK} backend/Dockerfile found"
else
    echo -e "    ${WARNING}backend/Dockerfile not found"
fi

if [ -f "frontend/Dockerfile" ]; then
    echo -e "    ${CHECK} frontend/Dockerfile found"
else
    echo -e "    ${WARNING}frontend/Dockerfile not found"
fi

# Check environment files
echo ""
echo -e "  ${INFO}Checking environment files:"
if [ -f ".env" ]; then
    echo -e "    ${CHECK} .env found"
else
    echo -e "    ${WARNING}.env not found"
fi

if [ -f ".env.example" ]; then
    echo -e "    ${CHECK} .env.example found"
else
    echo -e "    ${WARNING}.env.example not found"
fi

if [ -f ".env.production" ]; then
    echo -e "    ${CHECK} .env.production found"
else
    echo -e "    ${WARNING}.env.production not found"
fi

# Check database files
echo ""
echo -e "  ${INFO}Checking database files:"
if [ -f "database/tradesense_schema.sql" ]; then
    echo -e "    ${CHECK} database/tradesense_schema.sql found"
else
    echo -e "    ${WARNING}database/tradesense_schema.sql not found"
fi

if [ -f "database/init.sql" ]; then
    echo -e "    ${CHECK} database/init.sql found"
else
    echo -e "    ${WARNING}database/init.sql not found"
fi

echo ""

# ============================================================================
# STEP 3: Check Current Service Status
# ============================================================================
echo -e "${PURPLE}🔍 STEP 3: Current Service Status${NC}"
echo ""

# Check if any containers are running
if docker ps -q --filter "name=tradesense" | grep -q .; then
    echo -e "  ${INFO}Running TradeSense containers:"
    docker ps --filter "name=tradesense" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
else
    echo -e "  ${INFO}No TradeSense containers currently running"
fi

echo ""

# Check for stopped containers
if docker ps -a -q --filter "name=tradesense" | grep -q .; then
    echo -e "  ${INFO}All TradeSense containers (including stopped):"
    docker ps -a --filter "name=tradesense" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
else
    echo -e "  ${INFO}No TradeSense containers found"
fi

echo ""

# ============================================================================
# STEP 4: Identify Common Issues
# ============================================================================
echo -e "${PURPLE}🔍 STEP 4: Issue Detection${NC}"
echo ""

ISSUES_FOUND=0

# Issue 1: PostgreSQL healthcheck user mismatch
if grep -q "pg_isready -U tradesense_user" docker-compose.yml 2>/dev/null; then
    if grep -q "POSTGRES_USER: postgres" docker-compose.yml 2>/dev/null; then
        echo -e "  ${ERROR} Issue 1: PostgreSQL healthcheck user mismatch"
        echo -e "      Healthcheck uses 'tradesense_user' but POSTGRES_USER is 'postgres'"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
fi

# Issue 2: Port configuration consistency
if grep -q "PORT.*8000" docker-compose.yml 2>/dev/null; then
    if ! grep -q "8000:8000" docker-compose.yml 2>/dev/null; then
        echo -e "  ${WARNING} Issue 2: Port configuration may be inconsistent"
        echo -e "      Check if internal and external ports match"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
fi

# Issue 3: Missing required files
REQUIRED_FILES=("src/main.py" "requirements.txt" "database/tradesense_schema.sql")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "  ${ERROR} Issue 3: Required file missing: $file"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
done

# Issue 4: Environment variable consistency
if [ -f ".env" ] && [ -f "docker-compose.yml" ]; then
    if ! grep -q "REDIS_PASSWORD" .env 2>/dev/null; then
        echo -e "  ${WARNING} Issue 4: REDIS_PASSWORD not found in .env"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
fi

if [ $ISSUES_FOUND -eq 0 ]; then
    echo -e "  ${CHECK} No major issues detected in Docker configuration"
fi

echo ""

# ============================================================================
# STEP 5: Network and Volume Status
# ============================================================================
echo -e "${PURPLE}🔍 STEP 5: Network and Volume Status${NC}"
echo ""

# Check networks
if docker network ls | grep -q tradesense; then
    echo -e "  ${CHECK} TradeSense networks exist:"
    docker network ls | grep tradesense
else
    echo -e "  ${INFO}No TradeSense networks found (will be created on first run)"
fi

echo ""

# Check volumes
if docker volume ls | grep -q tradesense; then
    echo -e "  ${CHECK} TradeSense volumes exist:"
    docker volume ls | grep tradesense
else
    echo -e "  ${INFO}No TradeSense volumes found (will be created on first run)"
fi

echo ""

# ============================================================================
# STEP 6: Provide Fixes and Recommendations
# ============================================================================
echo -e "${PURPLE}🔧 STEP 6: Fixes and Recommendations${NC}"
echo ""

if [ $ISSUES_FOUND -gt 0 ]; then
    echo -e "${FIX} ${YELLOW}Issues detected. Here are the recommended fixes:${NC}"
    echo ""

    echo -e "  ${FIX} Fix 1: Create corrected docker-compose.yml"
    echo -e "      cp docker-compose-fixed.yml docker-compose.yml"
    echo ""

    echo -e "  ${FIX} Fix 2: Ensure environment file is properly configured"
    echo -e "      cp .env.example .env"
    echo -e "      # Edit .env with your actual values"
    echo ""

    echo -e "  ${FIX} Fix 3: Create missing database init file if needed"
    echo -e "      cp database/tradesense_schema.sql database/init.sql"
    echo ""

    echo -e "  ${FIX} Fix 4: Use corrected Dockerfile for backend"
    echo -e "      cp Dockerfile.backend-fixed Dockerfile.backend"
    echo ""

else
    echo -e "${CHECK} ${GREEN}Configuration looks good!${NC}"
fi

echo -e "${INFO} ${BLUE}Recommended deployment steps:${NC}"
echo ""
echo -e "  1. ${ROCKET} Start basic services first:"
echo -e "     docker-compose up -d postgres redis"
echo ""
echo -e "  2. ${ROCKET} Wait for databases to be ready (30 seconds)"
echo -e "     sleep 30"
echo ""
echo -e "  3. ${ROCKET} Start application services:"
echo -e "     docker-compose up -d backend frontend"
echo ""
echo -e "  4. ${ROCKET} Check service health:"
echo -e "     docker-compose ps"
echo -e "     curl http://localhost:8000/health"
echo ""
echo -e "  5. ${ROCKET} View logs if needed:"
echo -e "     docker-compose logs -f [service-name]"
echo ""

# ============================================================================
# STEP 7: Quick Test Commands
# ============================================================================
echo -e "${PURPLE}🧪 STEP 7: Quick Test Commands${NC}"
echo ""

echo -e "${INFO} ${BLUE}After deployment, test with these commands:${NC}"
echo ""
echo -e "  # Backend health check"
echo -e "  curl http://localhost:8000/health"
echo ""
echo -e "  # Frontend accessibility"
echo -e "  curl http://localhost:3000"
echo ""
echo -e "  # Database connectivity"
echo -e "  docker-compose exec postgres psql -U tradesense_user -d tradesense -c '\\dt'"
echo ""
echo -e "  # Redis connectivity"
echo -e "  docker-compose exec redis redis-cli -a tradesense_redis ping"
echo ""
echo -e "  # Test API endpoints"
echo -e "  curl http://localhost:8000/api/payment-simulation/pricing"
echo -e "  curl http://localhost:8000/api/market/morocco/IAM"
echo ""

# ============================================================================
# STEP 8: Auto-fix Option
# ============================================================================
echo -e "${PURPLE}🚀 STEP 8: Auto-fix Option${NC}"
echo ""

read -p "Would you like to attempt automatic fixes? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${FIX} Applying automatic fixes..."

    # Copy corrected files if they exist
    if [ -f "docker-compose-fixed.yml" ]; then
        echo -e "  ${CHECK} Using corrected docker-compose.yml"
        cp docker-compose-fixed.yml docker-compose.yml
    fi

    if [ -f "Dockerfile.backend-fixed" ]; then
        echo -e "  ${CHECK} Using corrected backend Dockerfile"
        cp Dockerfile.backend-fixed Dockerfile.backend
    fi

    # Create .env if it doesn't exist
    if [ ! -f ".env" ] && [ -f ".env.example" ]; then
        echo -e "  ${CHECK} Creating .env from example"
        cp .env.example .env
    fi

    # Create database init file if needed
    if [ ! -f "database/init.sql" ] && [ -f "database/tradesense_schema.sql" ]; then
        echo -e "  ${CHECK} Creating database init file"
        cp database/tradesense_schema.sql database/init.sql
    fi

    echo -e "  ${CHECK} Automatic fixes applied!"
    echo -e "  ${ROCKET} You can now run: docker-compose up -d"

else
    echo -e "${INFO} No automatic fixes applied. Use manual commands above."
fi

echo ""

# ============================================================================
# Final Summary
# ============================================================================
echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}                              SUMMARY${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

if [ $ISSUES_FOUND -eq 0 ]; then
    echo -e "${CHECK} ${GREEN}Docker configuration is ready for deployment!${NC}"
    echo -e "${ROCKET} ${GREEN}Run: bash start-docker.sh or docker-compose up -d${NC}"
else
    echo -e "${WARNING} ${YELLOW}Found $ISSUES_FOUND issue(s) that should be addressed${NC}"
    echo -e "${FIX} ${YELLOW}Apply the fixes above before deploying${NC}"
fi

echo ""
echo -e "${INFO} ${BLUE}TradeSense AI Docker Status Check Complete${NC}"
echo -e "${INFO} ${BLUE}For detailed deployment guide, see: DOCKER_DEPLOYMENT.md${NC}"
echo ""
echo -e "${BLUE}============================================================================${NC}"
