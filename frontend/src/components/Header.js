import React from 'react';
import './Header.css';

const Header = ({ serverStatus }) => {
  const getStatusColor = () => {
    switch (serverStatus) {
      case 'online':
        return '#10b981';
      case 'degraded':
        return '#f59e0b';
      case 'offline':
        return '#ef4444';
      default:
        return '#6b7280';
    }
  };

  const getStatusText = () => {
    switch (serverStatus) {
      case 'online':
        return '✓ AI Risk Engine: Active';
      case 'degraded':
        return '⚠ Degraded Performance';
      case 'offline':
        return '✗ Server Offline';
      default:
        return '⟳ Checking...';
    }
  };

  return (
    <header className="header">
      <div className="header-content">
        <div className="header-left">
          <h1 className="logo">TradeSense</h1>
          <nav className="nav">
            <button className="nav-item active">
              <span className="icon">📊</span> Dashboard
            </button>
            <button className="nav-item">
              <span className="icon">📈</span> Challenges
            </button>
            <button className="nav-item">
              <span className="icon">⚠️</span> Risk Monitor
            </button>
          </nav>
        </div>
        <div className="header-right">
          <div 
            className="status-badge" 
            style={{ backgroundColor: getStatusColor() }}
          >
            {getStatusText()}
          </div>
          <div className="user-info">
            <span className="welcome-text">Welcome,</span>
            <span className="user-name">Demo Trader</span>
            <button className="user-avatar">👤</button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
