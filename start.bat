@echo off
REM TradeSense AI - Quick Start Script for Windows
REM This script starts both backend and frontend for immediate testing

title TradeSense AI - Quick Start

echo.
echo  ████████╗██████╗  █████╗ ██████╗ ███████╗███████╗███████╗███╗   ██╗███████╗███████╗
echo  ╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔════╝██╔════╝████╗  ██║██╔════╝██╔════╝
echo     ██║   ██████╔╝███████║██║  ██║█████╗  ███████╗█████╗  ██╔██╗ ██║███████╗█████╗
echo     ██║   ██╔══██╗██╔══██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██║╚██╗██║╚════██║██╔══╝
echo     ██║   ██║  ██║██║  ██║██████╔╝███████╗███████║███████╗██║ ╚████║███████║███████╗
echo     ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝
echo.
echo     🚀 Professional Prop Trading Platform - Quick Start
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org
    pause
    exit /b 1
)

echo ✅ Python and Node.js are installed
echo.

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo 📦 Creating Python virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo ❌ Failed to create virtual environment
        pause
        exit /b 1
    )
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment already exists
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ❌ Failed to activate virtual environment
    pause
    exit /b 1
)

REM Install Python dependencies
if not exist ".venv\installed" (
    echo 📚 Installing Python dependencies...
    pip install --upgrade pip
    pip install Flask==3.0.0 Flask-CORS==4.0.0 Flask-SocketIO==5.3.6 Flask-JWT-Extended==4.6.0 Flask-SQLAlchemy==3.1.1 python-dotenv==1.0.0 marshmallow==3.20.1 redis==5.0.1
    if %errorlevel% neq 0 (
        echo ❌ Failed to install Python dependencies
        pause
        exit /b 1
    )
    echo installed > .venv\installed
    echo ✅ Python dependencies installed
) else (
    echo ✅ Python dependencies already installed
)

REM Create basic .env file if it doesn't exist
if not exist ".env" (
    echo 📝 Creating basic configuration file...
    (
        echo # TradeSense AI - Basic Configuration
        echo FLASK_ENV=development
        echo FLASK_DEBUG=True
        echo SECRET_KEY=dev-secret-key-for-demo-only
        echo JWT_SECRET_KEY=jwt-secret-key-for-demo-only
        echo DATABASE_URL=sqlite:///tradesense_demo.db
        echo REDIS_URL=redis://localhost:6379/0
        echo CORS_ORIGINS=http://localhost:3000,http://localhost:3001,http://localhost:5173
        echo LOG_LEVEL=INFO
        echo YAHOO_FINANCE_ENABLED=True
        echo MARKET_DATA_CACHE_TTL=60
    ) > .env
    echo ✅ Configuration file created
) else (
    echo ✅ Configuration file exists
)

REM Create logs directory
if not exist "logs" mkdir logs

REM Install frontend dependencies
if exist "frontend" (
    echo 🎨 Setting up frontend...
    cd frontend
    if not exist "node_modules" (
        echo 📚 Installing frontend dependencies...
        npm install --silent
        if %errorlevel% neq 0 (
            echo ❌ Failed to install frontend dependencies
            cd ..
            pause
            exit /b 1
        )
        echo ✅ Frontend dependencies installed
    ) else (
        echo ✅ Frontend dependencies already installed
    )
    cd ..
) else (
    echo ⚠️ Frontend directory not found, skipping frontend setup
)

echo.
echo 🎉 Setup completed successfully!
echo.
echo 📋 Demo Credentials:
echo    - Demo Trader: demo@tradesense.ai / demo123456
echo    - Admin User: admin@tradesense.ai / admin123456
echo.
echo 🚀 Starting TradeSense AI...
echo.

REM Start backend in a new window
start "TradeSense AI - Backend" cmd /c ".venv\Scripts\activate.bat && python run.py && pause"

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend if it exists
if exist "frontend" (
    echo 🎨 Starting frontend...
    start "TradeSense AI - Frontend" cmd /c "cd frontend && npm start"

    echo.
    echo ✅ TradeSense AI is starting up!
    echo.
    echo 🌐 Access URLs:
    echo    - Backend API: http://localhost:5000
    echo    - Frontend App: http://localhost:3000 (will open automatically)
    echo    - API Docs: http://localhost:5000/docs
    echo.
    echo 💡 Tips:
    echo    - Backend logs are in the Backend window
    echo    - Frontend will open in your browser automatically
    echo    - Use Ctrl+C in each window to stop services
    echo.

    REM Wait for frontend to start and open browser
    timeout /t 10 /nobreak >nul
    start http://localhost:3000

) else (
    echo.
    echo ✅ TradeSense AI Backend is starting!
    echo.
    echo 🌐 Access URLs:
    echo    - Backend API: http://localhost:5000
    echo    - API Docs: http://localhost:5000/docs
    echo    - Health Check: http://localhost:5000/health
    echo.
    echo 💡 Note: Frontend not found. Backend only mode.
    echo.
)

echo 📖 For more information, see README.md
echo 🆘 For support, visit: https://github.com/your-repo/tradesense/issues
echo.
echo Press any key to exit this window...
pause >nul
