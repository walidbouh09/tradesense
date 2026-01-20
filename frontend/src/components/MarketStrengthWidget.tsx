import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  LinearProgress,
  Chip,
  IconButton,
  Tooltip,
  Alert,
  Grid,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  TrendingFlat,
  Refresh,
  Info as InfoIcon,
} from '@mui/icons-material';
import { apiClient } from '../services/api';

interface MarketStrengthData {
  score: number;
  level: string;
  color: string;
  breakdown: Record<string, number>;
  total_instruments: number;
}

const MarketStrengthWidget: React.FC = () => {
  const [strength, setStrength] = useState<MarketStrengthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const fetchMarketStrength = async (showLoading = true) => {
    if (showLoading) {
      setLoading(true);
    }
    setError(null);

    try {
      const response = await apiClient.getMarketOverview();
      setStrength(response.data.overview.market_strength);
      setLastUpdate(new Date());
    } catch (err: any) {
      console.error('Failed to fetch market strength:', err);
      setError(err.response?.data?.error || 'Failed to load market strength');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMarketStrength();

    // Auto-refresh every 2 minutes
    const interval = setInterval(() => {
      fetchMarketStrength(false);
    }, 2 * 60 * 1000);

    return () => clearInterval(interval);
  }, []);

  const getStrengthIcon = (level: string) => {
    switch (level.toLowerCase()) {
      case 'strong bullish':
      case 'moderately bullish':
        return <TrendingUp color="success" />;
      case 'strong bearish':
      case 'moderately bearish':
        return <TrendingDown color="error" />;
      default:
        return <TrendingFlat color="warning" />;
    }
  };

  const getStrengthColor = (color: string) => {
    switch (color) {
      case 'green':
        return 'success';
      case 'light-green':
        return 'success';
      case 'yellow':
        return 'warning';
      case 'orange':
        return 'warning';
      case 'red':
        return 'error';
      default:
        return 'info';
    }
  };

  const getSentimentDescription = (level: string) => {
    const descriptions = {
      'Strong Bullish': 'Market is strongly bullish with most instruments trending up',
      'Moderately Bullish': 'Market shows bullish tendencies with positive momentum',
      'Neutral': 'Market is in neutral territory with mixed signals',
      'Moderately Bearish': 'Market shows bearish tendencies with negative momentum',
      'Strong Bearish': 'Market is strongly bearish with most instruments trending down',
    };
    return descriptions[level as keyof typeof descriptions] || 'Market sentiment analysis';
  };

  if (loading && !strength) {
    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="center" py={2}>
            <Typography variant="body2" color="text.secondary">
              Loading market strength...
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Alert severity="error" action={
            <IconButton size="small" onClick={() => fetchMarketStrength()}>
              <Refresh />
            </IconButton>
          }>
            {error}
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (!strength) return null;

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            {getStrengthIcon(strength.level)}
            <Typography variant="h6" component="h3">
              Market Strength
            </Typography>
          </Box>

          <Box display="flex" alignItems="center" gap={1}>
            <Tooltip title={getSentimentDescription(strength.level)}>
              <InfoIcon color="action" fontSize="small" />
            </Tooltip>
            <IconButton size="small" onClick={() => fetchMarketStrength()}>
              <Refresh />
            </IconButton>
          </Box>
        </Box>

        <Box mb={2}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
            <Typography variant="body2" color="text.secondary">
              Overall Sentiment
            </Typography>
            <Chip
              label={`${strength.score}% - ${strength.level}`}
              color={getStrengthColor(strength.color) as any}
              size="small"
            />
          </Box>
          <LinearProgress
            variant="determinate"
            value={strength.score}
            color={getStrengthColor(strength.color) as any}
            sx={{ height: 8, borderRadius: 4 }}
          />
        </Box>

        <Grid container spacing={1}>
          <Grid item xs={4}>
            <Box textAlign="center">
              <Typography variant="h6" color="success.main">
                {strength.breakdown.bullish}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Bullish
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={4}>
            <Box textAlign="center">
              <Typography variant="h6" color="warning.main">
                {strength.breakdown.neutral}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Neutral
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={4}>
            <Box textAlign="center">
              <Typography variant="h6" color="error.main">
                {strength.breakdown.bearish}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Bearish
              </Typography>
            </Box>
          </Grid>
        </Grid>

        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block', textAlign: 'center' }}>
          Based on {strength.total_instruments} major instruments • Updated {lastUpdate.toLocaleTimeString()}
        </Typography>
      </CardContent>
    </Card>
  );
};

export default MarketStrengthWidget;