#!/bin/bash

# TradeSense AI - Docker Quick Start Script
# This script builds and starts all Docker services

set -e

echo "=========================================="
echo "TradeSense AI - Docker Deployment"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}⚠️  Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}⚠️  Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

echo -e "${BLUE}📦 Step 1: Checking environment configuration...${NC}"
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating from .env.production...${NC}"
    cp .env.production .env
    echo -e "${GREEN}✓ .env file created${NC}"
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

echo ""
echo -e "${BLUE}🏗️  Step 2: Building Docker images...${NC}"
docker-compose build

echo ""
echo -e "${BLUE}🚀 Step 3: Starting services...${NC}"
docker-compose up -d

echo ""
echo -e "${BLUE}⏳ Step 4: Waiting for services to be healthy...${NC}"
sleep 10

# Check service health
echo ""
echo -e "${BLUE}🔍 Step 5: Checking service health...${NC}"

# Check PostgreSQL
if docker-compose exec -T postgres pg_isready -U tradesense_user &> /dev/null; then
    echo -e "${GREEN}✓ PostgreSQL is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  PostgreSQL is not ready yet${NC}"
fi

# Check Redis
if docker-compose exec -T redis redis-cli ping &> /dev/null; then
    echo -e "${GREEN}✓ Redis is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Redis is not ready yet${NC}"
fi

# Check Backend
if curl -sf http://localhost:5000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend API is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Backend API is not ready yet (may take a few more seconds)${NC}"
fi

# Check Frontend
if curl -sf http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Frontend is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend is not ready yet (may take a few more seconds)${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✅ TradeSense AI is starting!${NC}"
echo "=========================================="
echo ""
echo "🌐 Access the application:"
echo "   Frontend:  http://localhost:3000"
echo "   Backend:   http://localhost:5000"
echo "   Nginx:     http://localhost:80"
echo ""
echo "📊 View logs:"
echo "   docker-compose logs -f"
echo ""
echo "🛑 Stop services:"
echo "   docker-compose down"
echo ""
echo "📚 Full documentation:"
echo "   See DOCKER_DEPLOYMENT.md"
echo ""
echo "=========================================="
echo ""
echo -e "${BLUE}Opening browser in 5 seconds...${NC}"
sleep 5

# Try to open browser (works on most systems)
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:3000
elif command -v open &> /dev/null; then
    open http://localhost:3000
elif command -v start &> /dev/null; then
    start http://localhost:3000
else
    echo "Please open http://localhost:3000 in your browser"
fi
