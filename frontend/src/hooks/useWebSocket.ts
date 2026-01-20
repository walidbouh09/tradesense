import { useState, useEffect, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';

interface WebSocketMessage {
  type: string;
  challenge_id?: string;
  [key: string]: any;
}

export const useWebSocket = (challengeId?: string) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const socketRef = useRef<Socket | null>(null);

  const connect = useCallback(() => {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      console.warn('No auth token available for WebSocket connection');
      return;
    }

    // Connect to WebSocket server
    const socket = io('http://localhost:8000', {
      query: { token },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('WebSocket connected');
      setIsConnected(true);

      // Join challenge room if specified
      if (challengeId) {
        socket.emit('join_challenge', { challenge_id: challengeId });
      }
    });

    socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      setIsConnected(false);
    });

    socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      setIsConnected(false);
    });

    // Listen for challenge-specific events
    socket.on('EQUITY_UPDATED', (data) => {
      setLastMessage({
        type: 'EQUITY_UPDATED',
        challenge_id: data.challenge_id,
        ...data
      });
    });

    socket.on('CHALLENGE_STATUS_CHANGED', (data) => {
      setLastMessage({
        type: 'CHALLENGE_STATUS_CHANGED',
        challenge_id: data.challenge_id,
        ...data
      });
    });

    socket.on('RISK_ALERT', (data) => {
      setLastMessage({
        type: 'RISK_ALERT',
        challenge_id: data.challenge_id,
        ...data
      });
    });

    socket.on('TRADE_EXECUTED', (data) => {
      setLastMessage({
        type: 'TRADE_EXECUTED',
        challenge_id: data.challenge_id,
        ...data
      });
    });

    socket.on('CHALLENGE_FAILED', (data) => {
      setLastMessage({
        type: 'CHALLENGE_FAILED',
        challenge_id: data.challenge_id,
        ...data
      });
    });

    socket.on('CHALLENGE_FUNDED', (data) => {
      setLastMessage({
        type: 'CHALLENGE_FUNDED',
        challenge_id: data.challenge_id,
        ...data
      });
    });

    // Handle server messages
    socket.on('error', (data) => {
      console.error('WebSocket server error:', data.message);
    });

    socket.on('status', (data) => {
      console.log('WebSocket status:', data.message);
    });

    return socket;
  }, [challengeId]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
      setIsConnected(false);
    }
  }, []);

  const sendMessage = useCallback((event: string, data: any) => {
    if (socketRef.current && isConnected) {
      socketRef.current.emit(event, data);
    }
  }, [isConnected]);

  const joinChallenge = useCallback((challengeId: string) => {
    sendMessage('join_challenge', { challenge_id: challengeId });
  }, [sendMessage]);

  const leaveChallenge = useCallback((challengeId: string) => {
    sendMessage('leave_challenge', { challenge_id: challengeId });
  }, [sendMessage]);

  useEffect(() => {
    const socket = connect();

    return () => {
      if (socket) {
        socket.disconnect();
      }
    };
  }, [connect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnected,
    lastMessage,
    sendMessage,
    joinChallenge,
    leaveChallenge,
    disconnect,
  };
};