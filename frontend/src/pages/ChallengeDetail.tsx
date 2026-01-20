/* eslint-disable react-hooks/exhaustive-deps */
import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  CircularProgress,
  Alert,
  LinearProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  AccountBalance as BalanceIcon,
  Timeline as TimelineIcon,
  Warning as WarningIcon,
  CheckCircle as SuccessIcon,
} from '@mui/icons-material';

import { apiClient, ChallengeDetail as ChallengeDetailType } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';

const ChallengeDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [challenge, setChallenge] = useState<ChallengeDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // WebSocket for real-time updates specific to this challenge
  const { isConnected, lastMessage } = useWebSocket(id);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (id) {
      loadChallenge();
    }
  }, [id]);

  // Handle real-time updates
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (lastMessage && lastMessage.challenge_id === id) {
      handleWebSocketMessage(lastMessage);
    }
  }, [lastMessage, id]);

  const loadChallenge = async () => {
    if (!id) return;

    try {
      setLoading(true);
      const response = await apiClient.getChallenge(id);
      setChallenge(response.data);
    } catch (err) {
      setError('Failed to load challenge details');
      console.error('Error loading challenge:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleWebSocketMessage = (message: any) => {
    if (!challenge) return;

    if (message.type === 'EQUITY_UPDATED') {
      setChallenge(prev => prev ? {
        ...prev,
        current_equity: parseFloat(message.current_equity),
        last_trade_at: message.last_trade_at
      } : null);
    } else if (message.type === 'CHALLENGE_STATUS_CHANGED') {
      setChallenge(prev => prev ? {
        ...prev,
        status: message.new_status,
        ended_at: message.ended_at
      } : null);
    } else if (message.type === 'TRADE_EXECUTED') {
      // Could refresh trades list here
      loadChallenge();
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ACTIVE': return 'success';
      case 'FUNDED': return 'primary';
      case 'FAILED': return 'error';
      case 'PENDING': return 'warning';
      default: return 'default';
    }
  };

  const getRiskColor = (score?: number) => {
    if (!score) return 'default';
    if (score <= 30) return 'success';
    if (score <= 60) return 'warning';
    if (score <= 80) return 'error';
    return 'error';
  };

  const getRiskLabel = (score?: number) => {
    if (!score) return 'Unknown';
    if (score <= 30) return 'STABLE';
    if (score <= 60) return 'MONITOR';
    if (score <= 80) return 'HIGH_RISK';
    return 'CRITICAL';
  };

  const calculateProgress = () => {
    if (!challenge) return 0;
    if (challenge.status === 'FUNDED') return 100;
    if (challenge.status === 'FAILED') return 0;

    const progress = (challenge.current_equity / challenge.initial_balance) * 100;
    return Math.min(Math.max(progress, 0), 100);
  };

  const calculatePnL = () => {
    if (!challenge) return 0;
    return challenge.current_equity - challenge.initial_balance;
  };

  const calculateReturn = () => {
    if (!challenge) return 0;
    return ((challenge.current_equity / challenge.initial_balance) - 1) * 100;
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error || !challenge) {
    return (
      <Alert severity="error" sx={{ mt: 3 }}>
        {error || 'Challenge not found'}
      </Alert>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Challenge #{challenge.id.slice(-8)}
        </Typography>
        <Box display="flex" gap={2} alignItems="center">
          <Chip
            icon={isConnected ? <SuccessIcon /> : <WarningIcon />}
            label={isConnected ? 'Live Updates' : 'Offline'}
            color={isConnected ? 'success' : 'warning'}
            variant="outlined"
          />
          <Chip
            label={challenge.status}
            color={getStatusColor(challenge.status) as any}
          />
        </Box>
      </Box>

      {/* Overview Cards */}
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <BalanceIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Current Equity</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                ${challenge.current_equity.toFixed(2)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Initial: ${challenge.initial_balance.toFixed(2)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                {calculatePnL() >= 0 ? (
                  <TrendingUpIcon color="success" sx={{ mr: 1 }} />
                ) : (
                  <TrendingDownIcon color="error" sx={{ mr: 1 }} />
                )}
                <Typography variant="h6">Profit & Loss</Typography>
              </Box>
              <Typography
                variant="h4"
                color={calculatePnL() >= 0 ? 'success.main' : 'error.main'}
              >
                ${calculatePnL().toFixed(2)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {calculateReturn().toFixed(2)}% return
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <TimelineIcon color="info" sx={{ mr: 1 }} />
                <Typography variant="h6">Risk Score</Typography>
              </Box>
              <Typography variant="h4" color="info.main">
                75{/* Mock score for demo */}
              </Typography>
              <Chip
                label={getRiskLabel(75)}
                color={getRiskColor(75) as any}
                size="small"
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <TrendingUpIcon color="secondary" sx={{ mr: 1 }} />
                <Typography variant="h6">Trades</Typography>
              </Box>
              <Typography variant="h4" color="secondary.main">
                {challenge.total_trades}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Win Rate: {challenge.win_rate.toFixed(1)}%
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Progress Bar */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Challenge Progress
          </Typography>
          <Box display="flex" alignItems="center" mb={1}>
            <Box flex={1} mr={2}>
              <LinearProgress
                variant="determinate"
                value={calculateProgress()}
                sx={{ height: 10, borderRadius: 5 }}
              />
            </Box>
            <Typography variant="body2" color="text.secondary">
              {calculateProgress().toFixed(1)}%
            </Typography>
          </Box>
          <Typography variant="body2" color="text.secondary">
            Target: ${(challenge.initial_balance * 1.10).toFixed(2)} (10% profit target)
          </Typography>
        </CardContent>
      </Card>

      {/* Recent Trades */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Recent Trades
          </Typography>
          {challenge.trades.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No trades executed yet.
            </Typography>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Time</TableCell>
                    <TableCell>Symbol</TableCell>
                    <TableCell>Side</TableCell>
                    <TableCell align="right">Quantity</TableCell>
                    <TableCell align="right">Price</TableCell>
                    <TableCell align="right">PnL</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {challenge.trades.slice(-10).reverse().map((trade) => (
                    <TableRow key={trade.trade_id}>
                      <TableCell>
                        {new Date(trade.executed_at).toLocaleString()}
                      </TableCell>
                      <TableCell>{trade.symbol}</TableCell>
                      <TableCell>
                        <Chip
                          label={trade.side}
                          color={trade.side === 'BUY' ? 'success' : 'error'}
                          size="small"
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell align="right">{trade.quantity}</TableCell>
                      <TableCell align="right">${trade.price.toFixed(4)}</TableCell>
                      <TableCell align="right">
                        <Typography
                          color={trade.realized_pnl >= 0 ? 'success.main' : 'error.main'}
                        >
                          ${trade.realized_pnl.toFixed(2)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default ChallengeDetail;