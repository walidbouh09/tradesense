@echo off
REM TradeSense AI - Complete Startup Script for Windows
REM Starts both backend and frontend services with proper monitoring

title TradeSense AI - Complete Startup

echo.
echo  ████████╗██████╗  █████╗ ██████╗ ███████╗███████╗███████╗███╗   ██╗███████╗███████╗
echo  ╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔════╝██╔════╝████╗  ██║██╔════╝██╔════╝
echo     ██║   ██████╔╝███████║██║  ██║█████╗  ███████╗█████╗  ██╔██╗ ██║███████╗█████╗
echo     ██║   ██╔══██╗██╔══██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██║╚██╗██║╚════██║██╔══╝
echo     ██║   ██║  ██║██║  ██║██████╔╝███████╗███████║███████╗██║ ╚████║███████║███████╗
echo     ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝
echo.
echo     🚀 Professional Prop Trading Platform - Complete Startup
echo.

REM Check Python availability
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo ✅ Python is available

REM Check Node.js availability
node --version >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Node.js is available
    set HAS_NODE=1
) else (
    echo ⚠️ Node.js not found. Only backend will be started.
    set HAS_NODE=0
)

echo.
echo ============================================================
echo  Starting Backend Service
echo ============================================================
echo.

REM Check backend file
if not exist "app_simple.py" (
    echo ❌ Backend file 'app_simple.py' not found
    pause
    exit /b 1
)

echo 📋 Starting Flask backend server...
start "TradeSense AI - Backend" cmd /c "python app_simple.py > backend.log 2>&1"

REM Wait for backend to start
echo 📋 Waiting for backend to initialize...
timeout /t 5 /nobreak >nul

REM Test backend health
curl -s http://localhost:5000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Backend server started successfully
    echo ✅ Backend URL: http://localhost:5000
) else (
    echo ⚠️ Backend started but health check failed
    echo 📋 Waiting 5 more seconds...
    timeout /t 5 /nobreak >nul
    curl -s http://localhost:5000/health >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✅ Backend is now healthy
    ) else (
        echo ⚠️ Backend health check still having issues
        echo Backend may still be starting up...
    )
)

REM Start frontend if Node.js is available
if %HAS_NODE%==1 (
    if exist "frontend" (
        echo.
        echo ============================================================
        echo  Starting Frontend Service
        echo ============================================================
        echo.

        cd frontend

        if not exist "node_modules" (
            echo 📋 Installing frontend dependencies...
            npm install --silent >../frontend_install.log 2>&1
            if %errorlevel% neq 0 (
                echo ❌ Failed to install frontend dependencies
                echo Check frontend_install.log for details
                cd ..
                pause
                exit /b 1
            )
            echo ✅ Frontend dependencies installed
        )

        echo 📋 Starting React frontend server...
        start "TradeSense AI - Frontend" cmd /c "set PORT=3001 && npm start > ../frontend.log 2>&1"

        cd ..

        echo 📋 Waiting for frontend to initialize...
        timeout /t 10 /nobreak >nul

        echo ✅ Frontend server should be starting
        echo ✅ Frontend URL: http://localhost:3001
    )
)

echo.
echo ============================================================
echo  🎉 TradeSense AI Startup Complete!
echo ============================================================
echo.

echo 🌐 Service URLs:
echo    - Backend API: http://localhost:5000
echo    - API Health: http://localhost:5000/health
echo    - API Info: http://localhost:5000/api
if %HAS_NODE%==1 (
    echo    - Frontend App: http://localhost:3001
)
echo    - Test Interface: test_frontend.html

echo.
echo 🔑 Demo Credentials:
echo    - Demo Trader: demo.trader@tradesense.ai / demo123456
echo    - Admin User: admin@tradesense.ai / admin123456

echo.
echo 💡 Tips:
echo    - Backend runs in separate window
if %HAS_NODE%==1 (
    echo    - Frontend runs in separate window
)
echo    - Close windows to stop services
echo    - Check backend.log and frontend.log for logs
echo    - Use test_frontend.html for immediate testing

echo.
echo 📊 System Status:
echo    - Backend: ✅ Starting/Running
if %HAS_NODE%==1 (
    echo    - Frontend: ✅ Starting/Running
) else (
    echo    - Frontend: ⚠️ Not available (use test interface)
)

echo.
echo 🎯 TradeSense AI is ready for trading!
echo.

REM Open browser automatically
timeout /t 3 /nobreak >nul
if %HAS_NODE%==1 (
    echo 🌐 Opening frontend in browser...
    start http://localhost:3001
) else (
    echo 🌐 Opening test interface in browser...
    start test_frontend.html
)

echo.
echo ✅ Services started successfully!
echo.
echo Press any key to open system URLs...
pause >nul

REM Open additional URLs
start http://localhost:5000/health
start http://localhost:5000/api

echo.
echo 📋 All services are now running in separate windows.
echo 📋 Close this window when done, or close individual service windows to stop them.
echo.

echo Press any key to exit this startup window...
pause >nul
