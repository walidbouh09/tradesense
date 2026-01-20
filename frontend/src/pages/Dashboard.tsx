import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Button,
  Alert,
  CircularProgress,
  LinearProgress,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  AccountBalance as BalanceIcon,
  Assessment as AssessmentIcon,
  Warning as WarningIcon,
  CheckCircle as SuccessIcon,
  Add as AddIcon,
} from '@mui/icons-material';

import { apiClient, Challenge } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';
import MarketDataWidget from '../components/dashboard/MarketDataWidget';
import MarketOverview from '../components/MarketOverview';
import TradingViewChart from '../components/TradingViewChart';

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [riskScores, setRiskScores] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // WebSocket for real-time updates
  const { isConnected, lastMessage } = useWebSocket();

  useEffect(() => {
    loadChallenges();
  }, []);

  // Handle real-time updates
  useEffect(() => {
    if (lastMessage) {
      handleWebSocketMessage(lastMessage);
    }
  }, [lastMessage]);

  const loadChallenges = async () => {
    try {
      setLoading(true);
      const response = await apiClient.getChallenges();
      setChallenges(response.data.challenges);

      // Load risk scores for the challenges
      if (response.data.challenges.length > 0) {
        const riskResponse = await apiClient.getRiskScores();
        const riskMap: Record<string, any> = {};
        riskResponse.data.forEach((score: any) => {
          riskMap[score.challenge_id] = score;
        });
        setRiskScores(riskMap);
      }
    } catch (err) {
      setError('Failed to load challenges');
      console.error('Error loading challenges:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleWebSocketMessage = (message: any) => {
    // Handle real-time updates from WebSocket
    if (message.type === 'EQUITY_UPDATED' && message.challenge_id) {
      // Update challenge equity in real-time
      setChallenges(prev =>
        prev.map(challenge =>
          challenge.id === message.challenge_id
            ? { ...challenge, current_equity: parseFloat(message.current_equity) }
            : challenge
        )
      );
    } else if (message.type === 'CHALLENGE_STATUS_CHANGED' && message.challenge_id) {
      // Update challenge status in real-time
      setChallenges(prev =>
        prev.map(challenge =>
          challenge.id === message.challenge_id
            ? { ...challenge, status: message.new_status }
            : challenge
        )
      );
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ACTIVE': return 'success';
      case 'FUNDED': return 'primary';
      case 'FAILED': return 'error';
      case 'PENDING': return 'warning';
      default: return 'default';
    }
  };

  const calculateProgress = (challenge: Challenge) => {
    if (challenge.status === 'FUNDED') return 100;
    if (challenge.status === 'FAILED') return 0;

    // Calculate progress based on equity vs initial balance
    const progress = (challenge.current_equity / challenge.initial_balance) * 100;
    return Math.min(Math.max(progress, 0), 100);
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Trading Dashboard
        </Typography>
        <Box display="flex" gap={2} alignItems="center">
          <Chip
            icon={isConnected ? <SuccessIcon /> : <WarningIcon />}
            label={isConnected ? 'Live Updates Active' : 'Offline Mode'}
            color={isConnected ? 'success' : 'warning'}
            variant="outlined"
          />
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => navigate('/challenges')}
            size="large"
          >
            New Challenge
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {!challenges.length ? (
        <Card sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No Active Challenges
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={3}>
            Start your prop trading journey by creating your first challenge.
          </Typography>
          <Button
            variant="contained"
            size="large"
            startIcon={<AddIcon />}
            onClick={() => navigate('/challenges')}
          >
            Create Your First Challenge
          </Button>
        </Card>
      ) : (
        <Grid container spacing={3}>
          {/* Summary Cards */}
          <Grid item xs={12} md={3}>
            <Card className="trading-card">
              <CardContent>
                <Box display="flex" alignItems="center" mb={2}>
                  <BalanceIcon color="primary" sx={{ mr: 1 }} />
                  <Typography variant="h6">Active Challenges</Typography>
                </Box>
                <Typography variant="h3" color="primary">
                  {challenges.filter(c => c.status === 'ACTIVE').length}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card className="trading-card">
              <CardContent>
                <Box display="flex" alignItems="center" mb={2}>
                  <SuccessIcon color="success" sx={{ mr: 1 }} />
                  <Typography variant="h6">Successful</Typography>
                </Box>
                <Typography variant="h3" color="success.main">
                  {challenges.filter(c => c.status === 'FUNDED').length}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card className="trading-card">
              <CardContent>
                <Box display="flex" alignItems="center" mb={2}>
                  <AssessmentIcon color="warning" sx={{ mr: 1 }} />
                  <Typography variant="h6">Under Monitor</Typography>
                </Box>
                <Typography variant="h3" color="warning.main">
                  {challenges.filter(c => c.status === 'ACTIVE').length}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card className="trading-card">
              <CardContent>
                <Box display="flex" alignItems="center" mb={2}>
                  <TrendingUpIcon color="info" sx={{ mr: 1 }} />
                  <Typography variant="h6">Total PnL</Typography>
                </Box>
                <Typography variant="h3" color="info.main">
                  ${challenges.reduce((sum, c) => sum + (c.current_equity - c.initial_balance), 0).toFixed(0)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          {/* Market Overview */}
          <Grid item xs={12}>
            <MarketOverview />
          </Grid>

          {/* TradingView Chart */}
          <Grid item xs={12}>
            <TradingViewChart height={500} showVolume={true} autoRefresh={true} />
          </Grid>

          {/* Market Data Widget */}
          <Grid item xs={12}>
            <Box sx={{ mb: 3 }}>
              <MarketDataWidget />
            </Box>
          </Grid>

          {/* Challenge Cards */}
          {challenges.map(challenge => (
            <Grid item xs={12} md={6} lg={4} key={challenge.id}>
              <Card
                className="trading-card"
                onClick={() => navigate(`/challenges/${challenge.id}`)}
                sx={{ cursor: 'pointer' }}
              >
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="h6" noWrap sx={{ flex: 1 }}>
                      Challenge #{challenge.id.slice(-8)}
                    </Typography>
                    <Chip
                      label={challenge.status}
                      color={getStatusColor(challenge.status) as any}
                      size="small"
                    />
                  </Box>

                  <Box mb={2}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Current Equity
                    </Typography>
                    <Typography variant="h5" color="primary">
                      ${challenge.current_equity.toFixed(2)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Initial: ${challenge.initial_balance.toFixed(2)}
                    </Typography>
                  </Box>

                  <Box mb={2}>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                      <Typography variant="body2" color="text.secondary">
                        Progress
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {calculateProgress(challenge).toFixed(1)}%
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={calculateProgress(challenge)}
                      sx={{ height: 6, borderRadius: 3 }}
                    />
                  </Box>

                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Risk Score
                      </Typography>
                      <Chip
                        label={getRiskLabel(riskScores[challenge.id]?.score || 50)}
                        color={getRiskColor(riskScores[challenge.id]?.score || 50) as any}
                        size="small"
                        variant="outlined"
                      />
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                      {new Date(challenge.created_at).toLocaleDateString()}
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );
};

export default Dashboard;