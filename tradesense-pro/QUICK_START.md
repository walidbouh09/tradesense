# 🚀 TradeSense Pro - Quick Start Guide

**Get up and running in 5 minutes**

This guide will get you from zero to a fully functional TradeSense Pro development environment in under 5 minutes.

## ⚡ Prerequisites

Before starting, ensure you have:
- **Docker Desktop** installed and running
- **Git** installed
- **Node.js 18+** installed
- **Python 3.8+** installed

## 🎯 One-Command Setup

```bash
# Clone and setup everything
git clone https://github.com/your-org/tradesense-pro.git
cd tradesense-pro
./setup.sh
```

That's it! The setup script handles everything automatically.

## 🏃‍♂️ Manual Setup (Alternative)

If you prefer manual control:

### 1. Clone Repository
```bash
git clone https://github.com/your-org/tradesense-pro.git
cd tradesense-pro
```

### 2. Start Services
```bash
# Start database and cache
docker-compose up -d postgres redis

# Wait for services (30 seconds)
sleep 30
```

### 3. Backend Setup
```bash
cd backend
python -m venv ../venv
source ../venv/bin/activate  # On Windows: ..\venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Frontend Setup
```bash
cd ../frontend
npm install
```

### 5. Environment Files
```bash
# Copy example environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

## 🚀 Start Development

### Option 1: Helper Script
```bash
./scripts/start-dev.sh
```

### Option 2: Docker Compose
```bash
docker-compose up -d
```

### Option 3: Manual Start
```bash
# Terminal 1: Backend
cd backend
source ../venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

## 🌐 Access Your Application

Once everything is running, access:

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Database Admin**: http://localhost:5050 (if pgAdmin profile enabled)

## 🎯 Quick Test

### 1. Test Backend
```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy"}
```

### 2. Test Frontend
Open http://localhost:3000 - you should see the TradeSense Pro homepage.

### 3. Test Full Flow
1. Go to http://localhost:3000
2. Click "Register" and create an account
3. Login with your credentials
4. Create a new challenge
5. Execute a test trade

## 🔧 Configuration

### Essential Environment Variables

**Backend (.env)**
```env
DATABASE_URL=postgresql+asyncpg://tradesense:tradesense_password@localhost:5432/tradesense_pro
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
DEBUG=true
```

**Frontend (.env.local)**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

## 🛠️ Development Commands

### Backend
```bash
cd backend
source ../venv/bin/activate

# Run tests
pytest

# Format code
black app/
isort app/

# Database migrations
alembic upgrade head
```

### Frontend
```bash
cd frontend

# Run tests
npm test

# Format code
npm run format

# Type checking
npm run type-check

# Build for production
npm run build
```

## 🐳 Docker Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend frontend

# Stop all services
docker-compose down

# Reset database (⚠️ deletes all data)
docker-compose down -v
```

## 🔍 Troubleshooting

### Port Already in Use
```bash
# Check what's using ports 3000 or 8000
lsof -i :3000
lsof -i :8000

# Kill the process
kill -9 <PID>
```

### Database Connection Error
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Restart database
docker-compose restart postgres

# Check logs
docker-compose logs postgres
```

### Frontend Build Errors
```bash
# Clear cache and reinstall
rm -rf frontend/.next frontend/node_modules
cd frontend && npm install
```

### Python Virtual Environment Issues
```bash
# Recreate virtual environment
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

## 🎯 Next Steps

1. **Explore the API**: Visit http://localhost:8000/docs
2. **Check the Frontend**: Browse http://localhost:3000
3. **Run Tests**: Make sure everything works
4. **Read Documentation**: Check `/docs` folder for detailed guides
5. **Start Coding**: Begin implementing your features!

## 📚 Additional Resources

- **API Documentation**: http://localhost:8000/docs
- **Component Library**: http://localhost:6006 (if Storybook is running)
- **Database Admin**: http://localhost:5050
- **Monitoring**: http://localhost:3001 (if Grafana profile enabled)

## 🆘 Need Help?

- **Documentation**: Check the `/docs` folder
- **Issues**: Open a GitHub issue
- **Discord**: Join our development Discord
- **Email**: support@tradesense.ma

---

**You're all set! 🎉**

Your TradeSense Pro development environment is ready. Start building amazing trading features!