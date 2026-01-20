import React, { useState, useEffect } from "react";
import "./App.css";

function App() {
  const [backendStatus, setBackendStatus] = useState("checking");
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [user, setUser] = useState(null);
  const [loginForm, setLoginForm] = useState({
    email: "demo.trader@tradesense.ai",
    password: "demo123456",
  });

  // Check backend health on startup
  useEffect(() => {
    checkBackendHealth();
  }, []);

  const checkBackendHealth = async () => {
    try {
      const response = await fetch("http://localhost:5000/health");
      if (response.ok) {
        setBackendStatus("online");
      } else {
        setBackendStatus("offline");
      }
    } catch (error) {
      setBackendStatus("offline");
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch("http://localhost:5000/api/v1/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(loginForm),
      });

      if (response.ok) {
        const data = await response.json();
        setUser(data.user);
        setIsLoggedIn(true);
        localStorage.setItem("auth_token", data.tokens.access_token);
      } else {
        alert("Login failed");
      }
    } catch (error) {
      alert("Connection error");
    }
  };

  const handleLogout = () => {
    setIsLoggedIn(false);
    setUser(null);
    localStorage.removeItem("auth_token");
  };

  if (!isLoggedIn) {
    return (
      <div className="App">
        <div className="login-container">
          <div className="status-indicator">
            Backend Status:
            <span className={`status ${backendStatus}`}>{backendStatus}</span>
          </div>

          <div className="login-form">
            <h1>TradeSense AI</h1>
            <h2>Professional Prop Trading Platform</h2>

            <form onSubmit={handleLogin}>
              <div className="form-group">
                <label>Email:</label>
                <input
                  type="email"
                  value={loginForm.email}
                  onChange={(e) =>
                    setLoginForm({ ...loginForm, email: e.target.value })
                  }
                  required
                />
              </div>

              <div className="form-group">
                <label>Password:</label>
                <input
                  type="password"
                  value={loginForm.password}
                  onChange={(e) =>
                    setLoginForm({ ...loginForm, password: e.target.value })
                  }
                  required
                />
              </div>

              <button type="submit" className="login-btn">
                Login to TradeSense AI
              </button>
            </form>

            <div className="demo-info">
              <p>
                <strong>Demo Credentials:</strong>
              </p>
              <p>Email: demo.trader@tradesense.ai</p>
              <p>Password: demo123456</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="App">
      <header className="app-header">
        <h1>TradeSense AI Dashboard</h1>
        <div className="user-info">
          <span>Welcome, {user?.full_name || user?.email}</span>
          <button onClick={handleLogout} className="logout-btn">
            Logout
          </button>
        </div>
      </header>

      <main className="dashboard">
        <div className="welcome-message">
          <h2>🎉 Welcome to TradeSense AI!</h2>
          <p>
            Your professional prop trading platform is now running successfully.
          </p>

          <div className="system-status">
            <div className="status-card">
              <h3>Backend API</h3>
              <div className={`status-indicator ${backendStatus}`}>
                {backendStatus === "online" ? "✅ Online" : "❌ Offline"}
              </div>
              <p>http://localhost:5000</p>
            </div>

            <div className="status-card">
              <h3>Frontend</h3>
              <div className="status-indicator online">✅ Online</div>
              <p>http://localhost:3000</p>
            </div>
          </div>

          <div className="next-steps">
            <h3>🚀 What's Working:</h3>
            <ul>
              <li>✅ Flask Backend API with SQLAlchemy</li>
              <li>✅ JWT Authentication System</li>
              <li>✅ React Frontend Application</li>
              <li>✅ Database with Demo Data</li>
              <li>✅ Professional UI/UX Design</li>
              <li>✅ Real-time Trading Simulation</li>
              <li>✅ Portfolio Management</li>
              <li>✅ Challenge System</li>
            </ul>
          </div>

          <div className="api-endpoints">
            <h3>📊 Available API Endpoints:</h3>
            <ul>
              <li>POST /api/v1/auth/login - User login</li>
              <li>GET /api/v1/portfolios - Portfolio management</li>
              <li>POST /api/v1/trades - Execute trades</li>
              <li>GET /api/v1/challenges - Trading challenges</li>
              <li>GET /api/v1/market/symbols - Market data</li>
              <li>GET /health - System health check</li>
            </ul>
          </div>

          <div className="user-info-card">
            <h3>👤 User Information:</h3>
            <p>
              <strong>Name:</strong> {user?.full_name}
            </p>
            <p>
              <strong>Email:</strong> {user?.email}
            </p>
            <p>
              <strong>Role:</strong> {user?.role}
            </p>
            <p>
              <strong>Experience:</strong> {user?.experience_level}
            </p>
            <p>
              <strong>Status:</strong> {user?.status}
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
