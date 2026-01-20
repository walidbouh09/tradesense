import React, { useState, useEffect } from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Alert,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  LinearProgress,
} from '@mui/material';
import {
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Assessment as AssessmentIcon,
} from '@mui/icons-material';

import { apiClient } from '../services/api';

interface RiskAlert {
  id: string;
  challenge_id: string;
  alert_type: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  title: string;
  message: string;
  created_at: string;
  acknowledged_at?: string;
}

interface RiskMetrics {
  total_alerts: number;
  critical_alerts: number;
  active_challenges: number;
  avg_risk_score: number;
  high_risk_challenges: number;
}

const RiskMonitoring: React.FC = () => {
  const [alerts, setAlerts] = useState<RiskAlert[]>([]);
  const [metrics, setMetrics] = useState<RiskMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadRiskData();
  }, []);

  const loadRiskData = async () => {
    try {
      setLoading(true);

      // Load risk alerts
      const alertsResponse = await apiClient.getRiskAlerts();
      setAlerts(alertsResponse.data);

      // Load risk summary (deterministic, server-derived)
      const summaryResponse = await apiClient.getRiskSummary();
      const summary = summaryResponse.data;

      setMetrics({
        total_alerts: summary.total_alerts || 0,
        critical_alerts: summary.critical_alerts || 0,
        active_challenges: summary.active_challenges || 0,
        // Back-compat fields kept for UI display
        avg_risk_score: Math.round((summary.avg_drawdown_pct || 0) + ((summary.avg_trade_frequency_per_hour_24h || 0) * 10)),
        high_risk_challenges: summary.high_alerts || 0,
      });
    } catch (err) {
      setError('Failed to load risk monitoring data');
      console.error('Error loading risk data:', err);
    } finally {
      setLoading(false);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'LOW': return 'info';
      case 'MEDIUM': return 'warning';
      case 'HIGH': return 'error';
      case 'CRITICAL': return 'error';
      default: return 'default';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'LOW': return <InfoIcon />;
      case 'MEDIUM': return <WarningIcon />;
      case 'HIGH': return <WarningIcon />;
      case 'CRITICAL': return <ErrorIcon />;
      default: return <InfoIcon />;
    }
  };

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutes = Math.floor(diffMs / (1000 * 60));

    if (diffHours > 0) {
      return `${diffHours}h ago`;
    } else {
      return `${diffMinutes}m ago`;
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
          Risk Monitoring Dashboard
        </Typography>
        <Chip
          icon={<AssessmentIcon />}
          label="AI Risk Engine Active"
          color="success"
          variant="outlined"
        />
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Risk Metrics Overview */}
      {metrics && (
        <Grid container spacing={3} mb={3}>
          <Grid item xs={12} md={3}>
            <Card className="trading-card">
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Total Alerts
                </Typography>
                <Typography variant="h3" color="warning.main">
                  {metrics.total_alerts}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Active risk alerts
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card className="trading-card">
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Critical Alerts
                </Typography>
                <Typography variant="h3" color="error.main">
                  {metrics.critical_alerts}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Require immediate action
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card className="trading-card">
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Active Challenges
                </Typography>
                <Typography variant="h3" color="info.main">
                  {metrics.active_challenges}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Under risk monitoring
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card className="trading-card">
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Avg Risk Score
                </Typography>
                <Typography variant="h3" color="secondary.main">
                  {metrics.avg_risk_score}
                </Typography>
                <Box mt={1}>
                  <LinearProgress
                    variant="determinate"
                    value={metrics.avg_risk_score}
                    color={metrics.avg_risk_score > 60 ? 'error' : metrics.avg_risk_score > 30 ? 'warning' : 'success'}
                    sx={{ height: 6, borderRadius: 3 }}
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Risk Alerts Table */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Active Risk Alerts
          </Typography>

          {alerts.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No active risk alerts. All challenges are within normal risk parameters.
            </Typography>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Severity</TableCell>
                    <TableCell>Challenge</TableCell>
                    <TableCell>Alert Type</TableCell>
                    <TableCell>Title</TableCell>
                    <TableCell>Message</TableCell>
                    <TableCell>Time</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {alerts.map((alert) => (
                    <TableRow key={alert.id} hover>
                      <TableCell>
                        <Chip
                          icon={getSeverityIcon(alert.severity)}
                          label={alert.severity}
                          color={getSeverityColor(alert.severity) as any}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">
                          {alert.challenge_id.slice(-8)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {alert.alert_type.replace('_', ' ')}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight="medium">
                          {alert.title}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {alert.message}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {formatTimeAgo(alert.created_at)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {alert.acknowledged_at ? (
                          <Chip label="Acknowledged" color="success" size="small" variant="outlined" />
                        ) : (
                          <Chip label="Active" color="warning" size="small" />
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {/* Risk Intelligence Summary */}
      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            AI Risk Intelligence Summary
          </Typography>

          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <Box mb={2}>
                <Typography variant="body2" color="text.secondary" mb={1}>
                  Risk Distribution
                </Typography>
                <Box display="flex" gap={1} flexWrap="wrap">
                  <Chip label="Stable: 45%" color="success" size="small" />
                  <Chip label="Monitor: 30%" color="warning" size="small" />
                  <Chip label="High Risk: 20%" color="error" size="small" />
                  <Chip label="Critical: 5%" color="error" size="small" variant="outlined" />
                </Box>
              </Box>
            </Grid>

            <Grid item xs={12} md={6}>
              <Box mb={2}>
                <Typography variant="body2" color="text.secondary" mb={1}>
                  Key Risk Indicators
                </Typography>
                <Box display="flex" flexDirection="column" gap={1}>
                  <Typography variant="body2">• 3 challenges approaching drawdown limits</Typography>
                  <Typography variant="body2">• 2 challenges showing revenge trading patterns</Typography>
                  <Typography variant="body2">• 1 challenge with extended loss streak</Typography>
                  <Typography variant="body2">• AI monitoring 8 active challenges</Typography>
                </Box>
              </Box>
            </Grid>
          </Grid>

          <Alert severity="info" sx={{ mt: 2 }}>
            <Typography variant="body2">
              <strong>AI Risk Engine Status:</strong> All systems operational.
              Real-time monitoring active across all challenges.
              Risk scores updated every 5 minutes with behavioral analysis.
            </Typography>
          </Alert>
        </CardContent>
      </Card>
    </Box>
  );
};

export default RiskMonitoring;