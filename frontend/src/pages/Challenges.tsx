import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Button,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  CircularProgress,
  Fab,
} from '@mui/material';
import {
  Add as AddIcon,
  TrendingUp as TrendingUpIcon,
  AccountBalance as BalanceIcon,
  Timeline as TimelineIcon,
} from '@mui/icons-material';

import { apiClient, Challenge } from '../services/api';

const Challenges: React.FC = () => {
  const navigate = useNavigate();
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);

  const [newChallenge, setNewChallenge] = useState({
    initial_balance: 10000,
    rules: {
      max_daily_drawdown: 0.05,
      max_total_drawdown: 0.10,
      profit_target: 0.10,
    },
  });

  useEffect(() => {
    loadChallenges();
  }, []);

  const loadChallenges = async () => {
    try {
      setLoading(true);
      const response = await apiClient.getChallenges();
      setChallenges(response.data.challenges);
    } catch (err) {
      setError('Failed to load challenges');
      console.error('Error loading challenges:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateChallenge = async () => {
    try {
      setCreating(true);
      await apiClient.createChallenge(newChallenge);
      setCreateDialogOpen(false);
      setNewChallenge({
        initial_balance: 10000,
        rules: {
          max_daily_drawdown: 0.05,
          max_total_drawdown: 0.10,
          profit_target: 0.10,
        },
      });
      loadChallenges(); // Refresh the list
    } catch (err) {
      setError('Failed to create challenge');
      console.error('Error creating challenge:', err);
    } finally {
      setCreating(false);
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

  const getStatusDescription = (status: string) => {
    switch (status) {
      case 'ACTIVE': return 'Currently trading';
      case 'FUNDED': return 'Successfully completed - funds released';
      case 'FAILED': return 'Challenge failed - rules violated';
      case 'PENDING': return 'Awaiting activation';
      default: return 'Unknown status';
    }
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
          Trading Challenges
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setCreateDialogOpen(true)}
          size="large"
        >
          Create Challenge
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {!challenges.length ? (
        <Card sx={{ p: 6, textAlign: 'center' }}>
          <Typography variant="h5" color="text.secondary" gutterBottom>
            No Challenges Yet
          </Typography>
          <Typography variant="body1" color="text.secondary" mb={4}>
            Create your first prop trading challenge to start building your track record.
          </Typography>
          <Button
            variant="contained"
            size="large"
            startIcon={<AddIcon />}
            onClick={() => setCreateDialogOpen(true)}
          >
            Create Your First Challenge
          </Button>
        </Card>
      ) : (
        <Grid container spacing={3}>
          {challenges.map((challenge) => (
            <Grid item xs={12} md={6} lg={4} key={challenge.id}>
              <Card
                className="trading-card"
                onClick={() => navigate(`/challenges/${challenge.id}`)}
                sx={{ cursor: 'pointer' }}
              >
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="h6">
                      Challenge #{challenge.id.slice(-8)}
                    </Typography>
                    <Chip
                      label={challenge.status}
                      color={getStatusColor(challenge.status) as any}
                      size="small"
                    />
                  </Box>

                  <Typography variant="body2" color="text.secondary" mb={2}>
                    {getStatusDescription(challenge.status)}
                  </Typography>

                  <Grid container spacing={2} mb={2}>
                    <Grid item xs={6}>
                      <Box textAlign="center">
                        <BalanceIcon color="primary" sx={{ fontSize: 24, mb: 1 }} />
                        <Typography variant="body2" color="text.secondary">
                          Current Equity
                        </Typography>
                        <Typography variant="h6" color="primary">
                          ${challenge.current_equity.toFixed(0)}
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={6}>
                      <Box textAlign="center">
                        <TrendingUpIcon color="success" sx={{ fontSize: 24, mb: 1 }} />
                        <Typography variant="body2" color="text.secondary">
                          Initial Balance
                        </Typography>
                        <Typography variant="h6" color="success.main">
                          ${challenge.initial_balance.toFixed(0)}
                        </Typography>
                      </Box>
                    </Grid>
                  </Grid>

                  <Box mb={2}>
                    <Typography variant="body2" color="text.secondary" mb={1}>
                      Performance
                    </Typography>
                    <Box display="flex" justifyContent="space-between" alignItems="center">
                      <Typography variant="body2">
                        PnL: ${(challenge.current_equity - challenge.initial_balance).toFixed(2)}
                      </Typography>
                      <Typography variant="body2">
                        Return: {(((challenge.current_equity / challenge.initial_balance) - 1) * 100).toFixed(1)}%
                      </Typography>
                    </Box>
                  </Box>

                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="body2" color="text.secondary">
                      Started
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {new Date(challenge.started_at || challenge.created_at).toLocaleDateString()}
                    </Typography>
                  </Box>

                  {challenge.last_trade_at && (
                    <Box display="flex" justifyContent="space-between" alignItems="center">
                      <Typography variant="body2" color="text.secondary">
                        Last Trade
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {new Date(challenge.last_trade_at).toLocaleDateString()}
                      </Typography>
                    </Box>
                  )}

                  <Box mt={2}>
                    <Chip
                      label="AI Risk Monitoring Active"
                      size="small"
                      color="info"
                      variant="outlined"
                      icon={<TimelineIcon />}
                    />
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Create Challenge Dialog */}
      <Dialog
        open={createDialogOpen}
        onClose={() => !creating && setCreateDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Create New Trading Challenge</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Initial Balance ($)"
            type="number"
            value={newChallenge.initial_balance}
            onChange={(e) => setNewChallenge({
              ...newChallenge,
              initial_balance: parseFloat(e.target.value) || 10000
            })}
            margin="normal"
            helperText="Starting capital for your challenge"
          />

          <Typography variant="h6" sx={{ mt: 2, mb: 1 }}>
            Challenge Rules
          </Typography>

          <TextField
            fullWidth
            label="Max Daily Drawdown (%)"
            type="number"
            value={(newChallenge.rules.max_daily_drawdown * 100).toFixed(1)}
            onChange={(e) => setNewChallenge({
              ...newChallenge,
              rules: {
                ...newChallenge.rules,
                max_daily_drawdown: (parseFloat(e.target.value) || 5) / 100
              }
            })}
            margin="normal"
            helperText="Maximum daily loss allowed"
          />

          <TextField
            fullWidth
            label="Max Total Drawdown (%)"
            type="number"
            value={(newChallenge.rules.max_total_drawdown * 100).toFixed(1)}
            onChange={(e) => setNewChallenge({
              ...newChallenge,
              rules: {
                ...newChallenge.rules,
                max_total_drawdown: (parseFloat(e.target.value) || 10) / 100
              }
            })}
            margin="normal"
            helperText="Maximum total loss allowed"
          />

          <TextField
            fullWidth
            label="Profit Target (%)"
            type="number"
            value={(newChallenge.rules.profit_target * 100).toFixed(1)}
            onChange={(e) => setNewChallenge({
              ...newChallenge,
              rules: {
                ...newChallenge.rules,
                profit_target: (parseFloat(e.target.value) || 10) / 100
              }
            })}
            margin="normal"
            helperText="Profit target to complete challenge"
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setCreateDialogOpen(false)}
            disabled={creating}
          >
            Cancel
          </Button>
          <Button
            onClick={handleCreateChallenge}
            variant="contained"
            disabled={creating}
          >
            {creating ? <CircularProgress size={20} /> : 'Create Challenge'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Floating Action Button for Mobile */}
      <Fab
        color="primary"
        aria-label="add challenge"
        sx={{ position: 'fixed', bottom: 16, right: 16 }}
        onClick={() => setCreateDialogOpen(true)}
      >
        <AddIcon />
      </Fab>
    </Box>
  );
};

export default Challenges;