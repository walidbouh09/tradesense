/**
 * Challenge Dashboard Component
 *
 * Real-time trading dashboard that displays live equity updates,
 * status changes, and risk alerts using WebSocket connections.
 *
 * Features:
 * - Live equity updates without polling
 * - Real-time status change notifications
 * - Risk alert monitoring
 * - Connection status indicators
 * - Responsive design for trading platforms
 */

import React, { useState, useEffect } from 'react';
import { useLiveChallenge, useWebSocketStatus } from '../hooks/useLiveChallenge';

const ChallengeDashboard = ({ challengeId, authToken }) => {
  const {
    equityData,
    statusData,
    riskAlerts,
    isConnected,
    error,
    refresh,
    clearAlerts,
  } = useLiveChallenge(challengeId, authToken);

  const { isConnected: wsConnected } = useWebSocketStatus(authToken);

  // Local state for UI management
  const [lastUpdate, setLastUpdate] = useState(null);
  const [showAlerts, setShowAlerts] = useState(true);

  // Track last update timestamp
  useEffect(() => {
    if (equityData) {
      setLastUpdate(new Date());
    }
  }, [equityData]);

  // Format currency values
  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(value || 0);
  };

  // Format percentage values
  const formatPercent = (value) => {
    return `${(value || 0).toFixed(2)}%`;
  };

  // Get status color for UI
  const getStatusColor = (status) => {
    switch (status) {
      case 'ACTIVE': return 'text-green-600 bg-green-100';
      case 'PENDING': return 'text-yellow-600 bg-yellow-100';
      case 'FAILED': return 'text-red-600 bg-red-100';
      case 'FUNDED': return 'text-blue-600 bg-blue-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  // Get alert severity color
  const getAlertColor = (severity) => {
    switch (severity) {
      case 'HIGH': return 'border-red-500 bg-red-50';
      case 'MEDIUM': return 'border-yellow-500 bg-yellow-50';
      case 'LOW': return 'border-blue-500 bg-blue-50';
      default: return 'border-gray-500 bg-gray-50';
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header with Connection Status */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Challenge Dashboard
          </h1>
          <p className="text-gray-600">Challenge ID: {challengeId}</p>
        </div>

        <div className="flex items-center space-x-4">
          {/* Connection Status */}
          <div className={`flex items-center space-x-2 px-3 py-1 rounded-full text-sm ${
            wsConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
          }`}>
            <div className={`w-2 h-2 rounded-full ${
              wsConnected ? 'bg-green-500' : 'bg-red-500'
            }`} />
            <span>{wsConnected ? 'Live' : 'Disconnected'}</span>
          </div>

          {/* Last Update */}
          {lastUpdate && (
            <div className="text-sm text-gray-500">
              Last update: {lastUpdate.toLocaleTimeString()}
            </div>
          )}

          {/* Refresh Button */}
          <button
            onClick={refresh}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
            disabled={!wsConnected}
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          <strong>Connection Error:</strong> {error}
        </div>
      )}

      {/* Main Dashboard Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Equity Panel */}
        <div className="lg:col-span-2 space-y-6">
          {/* Current Status */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Challenge Status</h2>
            <div className="flex items-center justify-between">
              <div>
                <div className={`inline-flex px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(
                  statusData?.new_status || 'PENDING'
                )}`}>
                  {statusData?.new_status || 'PENDING'}
                </div>
                {statusData?.reason && (
                  <div className="text-sm text-gray-600 mt-1">
                    Reason: {statusData.reason}
                  </div>
                )}
              </div>
              {statusData?.changed_at && (
                <div className="text-sm text-gray-500">
                  Changed: {statusData.changed_at.toLocaleString()}
                </div>
              )}
            </div>
          </div>

          {/* Equity Overview */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Equity Overview</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {formatCurrency(equityData?.current_equity)}
                </div>
                <div className="text-sm text-gray-600">Current Equity</div>
              </div>

              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">
                  {formatCurrency(equityData?.max_equity_ever)}
                </div>
                <div className="text-sm text-gray-600">Peak Equity</div>
              </div>

              <div className="text-center">
                <div className="text-2xl font-bold text-purple-600">
                  {formatCurrency(equityData?.total_pnl)}
                </div>
                <div className="text-sm text-gray-600">Total P&L</div>
              </div>

              <div className="text-center">
                <div className="text-2xl font-bold text-orange-600">
                  {equityData?.total_trades || 0}
                </div>
                <div className="text-sm text-gray-600">Total Trades</div>
              </div>
            </div>
          </div>

          {/* Daily Performance */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Daily Performance</h2>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <div className="text-lg font-semibold text-blue-600">
                  {formatCurrency(equityData?.daily_start_equity)}
                </div>
                <div className="text-sm text-gray-600">Day Start</div>
              </div>

              <div className="text-center">
                <div className="text-lg font-semibold text-green-600">
                  {formatCurrency(equityData?.daily_max_equity)}
                </div>
                <div className="text-sm text-gray-600">Day High</div>
              </div>

              <div className="text-center">
                <div className="text-lg font-semibold text-red-600">
                  {formatCurrency(equityData?.daily_min_equity)}
                </div>
                <div className="text-sm text-gray-600">Day Low</div>
              </div>
            </div>
          </div>

          {/* Recent Trade */}
          {equityData && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold mb-4">Latest Trade</h2>
              <div className="flex justify-between items-center">
                <div>
                  <div className="text-lg font-semibold">
                    {equityData.trade_symbol}
                  </div>
                  <div className="text-sm text-gray-600">
                    {equityData.executed_at?.toLocaleString()}
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-lg font-semibold ${
                    (equityData.trade_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {formatCurrency(equityData.trade_pnl)}
                  </div>
                  <div className="text-sm text-gray-600">Trade P&L</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Risk Alerts Panel */}
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Risk Alerts</h2>
              <div className="flex space-x-2">
                <button
                  onClick={() => setShowAlerts(!showAlerts)}
                  className="px-3 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200"
                >
                  {showAlerts ? 'Hide' : 'Show'}
                </button>
                <button
                  onClick={clearAlerts}
                  className="px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200"
                >
                  Clear
                </button>
              </div>
            </div>

            {showAlerts && (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {riskAlerts.length === 0 ? (
                  <div className="text-center text-gray-500 py-4">
                    No active alerts
                  </div>
                ) : (
                  riskAlerts.map((alert) => (
                    <div
                      key={alert.id}
                      className={`p-3 rounded border-l-4 ${getAlertColor(alert.severity)}`}
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="font-medium text-sm">{alert.title}</div>
                          <div className="text-xs text-gray-600 mt-1">{alert.message}</div>
                          <div className="text-xs text-gray-500 mt-1">
                            {alert.timestamp.toLocaleTimeString()}
                          </div>
                        </div>
                        <div className={`px-2 py-1 rounded text-xs font-medium ${
                          alert.severity === 'HIGH' ? 'bg-red-200 text-red-800' :
                          alert.severity === 'MEDIUM' ? 'bg-yellow-200 text-yellow-800' :
                          'bg-blue-200 text-blue-800'
                        }`}>
                          {alert.severity}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Connection Details */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Connection</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">WebSocket:</span>
                <span className={wsConnected ? 'text-green-600' : 'text-red-600'}>
                  {wsConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Live Updates:</span>
                <span className={isConnected ? 'text-green-600' : 'text-red-600'}>
                  {isConnected ? 'Active' : 'Inactive'}
                </span>
              </div>
              {lastUpdate && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Last Update:</span>
                  <span className="text-gray-800">
                    {lastUpdate.toLocaleTimeString()}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Status Change Notifications */}
      {statusData && (
        <div className="fixed bottom-4 right-4 max-w-sm">
          <div className={`p-4 rounded-lg shadow-lg border-l-4 ${
            statusData.new_status === 'FAILED' ? 'bg-red-50 border-red-500' :
            statusData.new_status === 'FUNDED' ? 'bg-green-50 border-green-500' :
            'bg-blue-50 border-blue-500'
          }`}>
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">
                  Challenge {statusData.new_status}
                </div>
                {statusData.reason && (
                  <div className="text-sm text-gray-600">
                    {statusData.reason}
                  </div>
                )}
              </div>
              <button
                onClick={() => setStatusData(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                ×
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChallengeDashboard;