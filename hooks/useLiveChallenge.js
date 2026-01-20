/**
 * React hook for real-time challenge updates via WebSocket
 *
 * Provides live updates for equity changes, status transitions, and risk alerts
 * without requiring page refreshes or polling.
 *
 * Features:
 * - Automatic subscription management
 * - Challenge-specific isolation
 * - Reconnection handling
 * - Type-safe event handling
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import io from 'socket.io-client';

// WebSocket connection management
let socket = null;
const challengeSubscriptions = new Map(); // challengeId -> Set of callbacks

/**
 * Get or create WebSocket connection
 * Reuses connection across multiple hook instances for efficiency
 */
function getSocket(token) {
  if (!socket) {
    const socketUrl = process.env.REACT_APP_WS_URL || 'http://localhost:5000';

    socket = io(socketUrl, {
      query: { token },
      transports: ['websocket', 'polling'], // Fallback to polling if needed
      timeout: 20000,
      forceNew: false, // Reuse connections
    });

    // Global error handling
    socket.on('error', (error) => {
      console.error('WebSocket error:', error);
    });

    socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
    });

    socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
    });
  }

  return socket;
}

/**
 * Hook for live challenge updates
 *
 * @param {string} challengeId - The challenge ID to subscribe to
 * @param {string} token - JWT authentication token
 * @returns {Object} Live challenge data and connection status
 */
export function useLiveChallenge(challengeId, token) {
  const [equityData, setEquityData] = useState(null);
  const [statusData, setStatusData] = useState(null);
  const [riskAlerts, setRiskAlerts] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);

  // Refs for cleanup and avoiding stale closures
  const challengeIdRef = useRef(challengeId);
  const tokenRef = useRef(token);

  // Update refs when props change
  useEffect(() => {
    challengeIdRef.current = challengeId;
    tokenRef.current = token;
  }, [challengeId, token]);

  // Initialize WebSocket connection and subscribe to challenge
  useEffect(() => {
    if (!challengeId || !token) {
      setError('Challenge ID and authentication token required');
      return;
    }

    const socket = getSocket(token);

    // Connection status tracking
    const handleConnect = () => {
      setIsConnected(true);
      setError(null);

      // Join challenge room after connection
      socket.emit('join_challenge', { challenge_id: challengeId });
    };

    const handleDisconnect = () => {
      setIsConnected(false);
    };

    const handleError = (error) => {
      setError(error.message || 'WebSocket connection failed');
      setIsConnected(false);
    };

    // Event handlers
    const handleEquityUpdate = useCallback((data) => {
      if (data.challenge_id === challengeId) {
        setEquityData({
          current_equity: parseFloat(data.current_equity),
          previous_equity: parseFloat(data.previous_equity),
          max_equity_ever: parseFloat(data.max_equity_ever),
          daily_start_equity: parseFloat(data.daily_start_equity),
          daily_max_equity: parseFloat(data.daily_max_equity),
          daily_min_equity: parseFloat(data.daily_min_equity),
          total_pnl: parseFloat(data.total_pnl),
          total_trades: data.total_trades,
          last_trade_at: new Date(data.last_trade_at),
          trade_pnl: parseFloat(data.trade_pnl),
          trade_symbol: data.trade_symbol,
          executed_at: new Date(data.executed_at),
          timestamp: new Date(), // When we received the update
        });
      }
    }, [challengeId]);

    const handleStatusChange = useCallback((data) => {
      if (data.challenge_id === challengeId) {
        setStatusData({
          old_status: data.old_status,
          new_status: data.new_status,
          reason: data.reason,
          changed_at: new Date(data.changed_at),
          timestamp: new Date(), // When we received the update
        });
      }
    }, [challengeId]);

    const handleRiskAlert = useCallback((data) => {
      if (data.challenge_id === challengeId) {
        const alert = {
          id: `${data.alert_type}_${Date.now()}`, // Simple ID generation
          type: data.alert_type,
          severity: data.severity,
          title: data.title,
          message: data.message,
          timestamp: new Date(),
          data: data, // Full alert data for advanced usage
        };

        setRiskAlerts(prev => {
          // Keep only last 10 alerts to prevent memory leaks
          const newAlerts = [alert, ...prev].slice(0, 10);
          return newAlerts;
        });
      }
    }, [challengeId]);

    const handleJoinedChallenge = useCallback((data) => {
      if (data.challenge_id === challengeId) {
        console.log(`Subscribed to challenge ${challengeId} updates`);
      }
    }, [challengeId]);

    // Set up event listeners
    socket.on('connect', handleConnect);
    socket.on('disconnect', handleDisconnect);
    socket.on('error', handleError);
    socket.on('equity_updated', handleEquityUpdate);
    socket.on('challenge_status_changed', handleStatusChange);
    socket.on('risk_alert', handleRiskAlert);
    socket.on('joined_challenge', handleJoinedChallenge);

    // If already connected, join room immediately
    if (socket.connected) {
      socket.emit('join_challenge', { challenge_id: challengeId });
    }

    // Cleanup function
    return () => {
      // Remove event listeners
      socket.off('connect', handleConnect);
      socket.off('disconnect', handleDisconnect);
      socket.off('error', handleError);
      socket.off('equity_updated', handleEquityUpdate);
      socket.off('challenge_status_changed', handleStatusChange);
      socket.off('risk_alert', handleRiskAlert);
      socket.off('joined_challenge', handleJoinedChallenge);

      // Leave challenge room
      if (socket.connected) {
        socket.emit('leave_challenge', { challenge_id: challengeId });
      }
    };
  }, [challengeId, token]);

  // Manual refresh function (useful for testing or forced updates)
  const refresh = useCallback(() => {
    if (socket && socket.connected && challengeId) {
      socket.emit('join_challenge', { challenge_id: challengeId });
    }
  }, [challengeId]);

  // Clear alerts function
  const clearAlerts = useCallback(() => {
    setRiskAlerts([]);
  }, []);

  return {
    // Live data
    equityData,
    statusData,
    riskAlerts,

    // Connection status
    isConnected,
    error,

    // Utility functions
    refresh,
    clearAlerts,
  };
}

/**
 * Hook for monitoring WebSocket connection status globally
 * Useful for showing connection indicators in the UI
 */
export function useWebSocketStatus(token) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastConnected, setLastConnected] = useState(null);
  const [lastDisconnected, setLastDisconnected] = useState(null);

  useEffect(() => {
    if (!token) return;

    const socket = getSocket(token);

    const handleConnect = () => {
      setIsConnected(true);
      setLastConnected(new Date());
    };

    const handleDisconnect = () => {
      setIsConnected(false);
      setLastDisconnected(new Date());
    };

    socket.on('connect', handleConnect);
    socket.on('disconnect', handleDisconnect);

    // Set initial status
    setIsConnected(socket.connected);

    return () => {
      socket.off('connect', handleConnect);
      socket.off('disconnect', handleDisconnect);
    };
  }, [token]);

  return {
    isConnected,
    lastConnected,
    lastDisconnected,
  };
}

export default useLiveChallenge;