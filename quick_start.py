#!/usr/bin/env python3
"""
TradeSense AI - Quick Start Script
All-in-one startup and test script that works immediately.
"""

import json
import os
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen


# Minimal Flask-like server
class TradeSenseHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            response = {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat(),
            }
            self.wfile.write(json.dumps(response).encode())

        elif self.path == "/api":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            response = {
                "name": "TradeSense AI API",
                "version": "v1",
                "status": "operational",
                "endpoints": ["/health", "/api", "/api/v1/auth/login"],
            }
            self.wfile.write(json.dumps(response).encode())

        elif self.path == "/api/v1/market/symbols":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            response = {
                "symbols": [
                    {"symbol": "EURUSD", "name": "Euro / US Dollar"},
                    {"symbol": "GBPUSD", "name": "British Pound / US Dollar"},
                    {"symbol": "AAPL", "name": "Apple Inc."},
                    {"symbol": "GOOGL", "name": "Alphabet Inc."},
                ]
            }
            self.wfile.write(json.dumps(response).encode())

        elif self.path == "/api/v1/portfolios":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            response = {
                "portfolios": [
                    {
                        "id": "1",
                        "name": "Demo Portfolio",
                        "balance": 10000.00,
                        "pnl": 250.50,
                        "trades": 15,
                    }
                ]
            }
            self.wfile.write(json.dumps(response).encode())

        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"error": "Not found"}')

    def do_POST(self):
        if self.path == "/api/v1/auth/login":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)

            try:
                data = json.loads(post_data.decode())
                email = data.get("email", "")
                password = data.get("password", "")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                if email == "demo.trader@tradesense.ai" and password == "demo123456":
                    response = {
                        "message": "Login successful",
                        "user": {
                            "id": "2",
                            "email": "demo.trader@tradesense.ai",
                            "full_name": "Demo Trader",
                            "role": "trader",
                        },
                        "tokens": {
                            "access_token": "demo_token_123",
                            "expires_in": 3600,
                        },
                    }
                else:
                    self.send_response(401)
                    response = {"error": {"message": "Invalid credentials"}}

                self.wfile.write(json.dumps(response).encode())

            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {format % args}")


def start_server():
    """Start the TradeSense backend server."""
    server_address = ("", 5000)
    httpd = HTTPServer(server_address, TradeSenseHandler)

    print("🚀 TradeSense AI Backend Server")
    print("=" * 50)
    print("🌐 Server running on: http://localhost:5000")
    print("📊 Health check: http://localhost:5000/health")
    print("📚 API info: http://localhost:5000/api")
    print("🔑 Demo Login: demo.trader@tradesense.ai / demo123456")
    print("🛑 Press Ctrl+C to stop")
    print("=" * 50)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        httpd.server_close()


def test_server():
    """Test server connectivity."""
    max_retries = 10
    for i in range(max_retries):
        try:
            with urlopen("http://localhost:5000/health", timeout=2) as response:
                if response.status == 200:
                    print("✅ Server is responding")
                    return True
        except URLError:
            time.sleep(1)

    print("❌ Server not responding after 10 seconds")
    return False


def create_test_page():
    """Create a simple test page."""
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>TradeSense AI - Quick Test</title>
    <style>
        body { font-family: Arial; background: #0a0e27; color: white; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { color: #42a5f5; font-size: 2.5rem; }
        .status { background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; margin: 20px 0; }
        .btn { background: #42a5f5; color: white; border: none; padding: 10px 20px; margin: 10px; border-radius: 5px; cursor: pointer; }
        .btn:hover { background: #1976d2; }
        .response { background: rgba(0,0,0,0.5); padding: 15px; border-radius: 5px; margin: 10px 0; font-family: monospace; }
        .form { margin: 20px 0; }
        .form input { padding: 10px; margin: 5px; border-radius: 5px; border: none; width: 250px; }
        .success { color: #4caf50; }
        .error { color: #f44336; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>TradeSense AI</h1>
            <p>Quick Test Interface</p>
        </div>

        <div class="status">
            <h3>Server Status</h3>
            <div id="status">Checking...</div>
        </div>

        <div class="status">
            <h3>Login Test</h3>
            <div class="form">
                <input type="email" id="email" placeholder="Email" value="demo.trader@tradesense.ai">
                <input type="password" id="password" placeholder="Password" value="demo123456">
                <button class="btn" onclick="testLogin()">Login</button>
            </div>
        </div>

        <div class="status">
            <h3>API Tests</h3>
            <button class="btn" onclick="testEndpoint('/health')">Health Check</button>
            <button class="btn" onclick="testEndpoint('/api')">API Info</button>
            <button class="btn" onclick="testEndpoint('/api/v1/portfolios')">Portfolios</button>
            <button class="btn" onclick="testEndpoint('/api/v1/market/symbols')">Market Data</button>
        </div>

        <div class="status">
            <h3>Response</h3>
            <div id="response" class="response">Ready for testing...</div>
        </div>
    </div>

    <script>
        const API_BASE = 'http://localhost:5000';

        async function checkStatus() {
            try {
                const response = await fetch(API_BASE + '/health');
                if (response.ok) {
                    document.getElementById('status').innerHTML = '<span class="success">✅ Server Online</span>';
                } else {
                    document.getElementById('status').innerHTML = '<span class="error">❌ Server Error</span>';
                }
            } catch (error) {
                document.getElementById('status').innerHTML = '<span class="error">❌ Server Offline</span>';
            }
        }

        async function testEndpoint(endpoint) {
            try {
                const response = await fetch(API_BASE + endpoint);
                const data = await response.json();
                document.getElementById('response').textContent =
                    'Endpoint: ' + endpoint + '\\n' +
                    'Status: ' + response.status + '\\n' +
                    'Response:\\n' + JSON.stringify(data, null, 2);
            } catch (error) {
                document.getElementById('response').textContent = 'Error: ' + error.message;
            }
        }

        async function testLogin() {
            try {
                const email = document.getElementById('email').value;
                const password = document.getElementById('password').value;

                const response = await fetch(API_BASE + '/api/v1/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email, password})
                });

                const data = await response.json();
                document.getElementById('response').textContent =
                    'Login Test\\n' +
                    'Status: ' + response.status + '\\n' +
                    'Response:\\n' + JSON.stringify(data, null, 2);
            } catch (error) {
                document.getElementById('response').textContent = 'Login Error: ' + error.message;
            }
        }

        // Check status on load
        checkStatus();
        setInterval(checkStatus, 10000);
    </script>
</body>
</html>"""

    with open("quick_test.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    return os.path.abspath("quick_test.html")


def main():
    """Main function."""
    print("🚀 TradeSense AI - Quick Start")
    print("=" * 40)

    # Start server in a separate thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    print("📋 Starting server...")
    time.sleep(3)

    # Test server
    if test_server():
        print("✅ Server started successfully!")

        # Create and open test page
        test_page = create_test_page()
        print(f"🌐 Created test page: {test_page}")

        try:
            webbrowser.open(f"file://{test_page}")
            print("🌐 Opening test page in browser...")
        except:
            print("⚠️  Please manually open: quick_test.html")

        print("\n" + "=" * 40)
        print("🎉 TradeSense AI is ready!")
        print("📍 Backend: http://localhost:5000")
        print("🔑 Demo: demo.trader@tradesense.ai / demo123456")
        print("🛑 Press Ctrl+C to stop")
        print("=" * 40)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Shutting down TradeSense AI...")

    else:
        print("❌ Failed to start server")
        print("💡 Try running manually: python -m http.server 5000")


if __name__ == "__main__":
    main()
