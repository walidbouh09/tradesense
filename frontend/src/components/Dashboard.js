import React, { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import './Dashboard.css';

const Dashboard = () => {
  const [stats, setStats] = useState({
    activeChallenges: 0,
    successful: 0,
    underMonitor: 0,
    totalPnL: 0
  });
  const [challenges, setChallenges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [offlineMode, setOfflineMode] = useState(false);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      // Fetch challenges (mock data for now)
      setStats({
        activeChallenges: 0,
        successful: 0,
        underMonitor: 0,
        totalPnL: 0
      });
      setChallenges([
        {
          id: '22c12a12',
          status: 'PENDING',
          tier: 'STARTER',
          balance: 10000,
          pnl: 0,
          createdAt: new Date().toISOString()
        }
      ]);
      setLoading(false);
      setOfflineMode(false);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setOfflineMode(true);
      setLoading(false);
      toast.error('Failed to load dashboard data');
    }
  };

  const handleNewChallenge = () => {
    toast.success('Opening challenge creation...');
    // Navigate to challenge creation
  };

  if (loading) {
    return (
      <div className="dashboard-loading">
        <div className="spinner"></div>
        <p>Loading dashboard...</p>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1 className="dashboard-title">Trading Dashboard</h1>
        <div className="dashboard-actions">
          {offlineMode && (
            <span className="offline-badge">⚠️ Offline Mode</span>
          )}
          <button className="btn-primary" onClick={handleNewChallenge}>
            <span className="icon">+</span> New Challenge
          </button>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon blue">🏛️</div>
          <div className="stat-content">
            <h3 className="stat-label">Active Challenges</h3>
            <p className="stat-value">{stats.activeChallenges}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon green">✓</div>
          <div className="stat-content">
            <h3 className="stat-label">Successful</h3>
            <p className="stat-value">{stats.successful}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon orange">⚠️</div>
          <div className="stat-content">
            <h3 className="stat-label">Under Monitor</h3>
            <p className="stat-value">{stats.underMonitor}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon purple">📈</div>
          <div className="stat-content">
            <h3 className="stat-label">Total PnL</h3>
            <p className="stat-value">${stats.totalPnL.toFixed(2)}</p>
          </div>
        </div>
      </div>

      <div className="challenges-section">
        <h2 className="section-title">Recent Challenges</h2>
        {challenges.length === 0 ? (
          <div className="empty-state">
            <p className="empty-icon">📊</p>
            <p className="empty-text">No challenges yet</p>
            <p className="empty-subtext">Create your first challenge to start trading</p>
            <button className="btn-secondary" onClick={handleNewChallenge}>
              Create Challenge
            </button>
          </div>
        ) : (
          <div className="challenges-list">
            {challenges.map(challenge => (
              <div key={challenge.id} className="challenge-card">
                <div className="challenge-header">
                  <h3 className="challenge-id">Challenge #{challenge.id}</h3>
                  <span className={`challenge-status status-${challenge.status.toLowerCase()}`}>
                    {challenge.status}
                  </span>
                </div>
                <div className="challenge-details">
                  <div className="detail-item">
                    <span className="detail-label">Tier:</span>
                    <span className="detail-value">{challenge.tier}</span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">Balance:</span>
                    <span className="detail-value">${challenge.balance.toLocaleString()}</span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">PnL:</span>
                    <span className={`detail-value ${challenge.pnl >= 0 ? 'positive' : 'negative'}`}>
                      ${challenge.pnl.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
