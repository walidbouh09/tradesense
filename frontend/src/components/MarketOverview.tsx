import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Grid,
  Box,
  Chip,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
  LinearProgress,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Refresh,
  Error as ErrorIcon,
  CheckCircle,
  Warning,
  Info,
} from '@mui/icons-material';
import { apiClient } from '../services/api';

interface MarketInstrument {
  name: string;
  symbol: string;
  current_price?: number;
  previous_close?: number;
  change?: number;
  change_percent?: number;
  type: string;
  last_updated?: string;
  status: 'online' | 'offline' | 'error';
  error?: string;
}

interface MarketStrength {
  score: number;
  level: string;
  color: string;
  breakdown: Record<string, number>;
  total_instruments: number;
}

interface MarketOverviewData {
  instruments: Record<string, MarketInstrument>;
  market_strength: MarketStrength;
  last_updated: string;
  status: string;
  error?: string;
}

const MarketOverview: React.FC = () => {
  const [data, setData] = useState<MarketOverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const fetchMarketOverview = async (showLoading = true) => {
    if (showLoading) {
      setLoading(true);
    }
    setError(null);

    try {
      const response = await apiClient.getMarketOverview();
      setData(response.data.overview);
      setLastRefresh(new Date());
    } catch (err: any) {
      console.error('Failed to fetch market overview:', err);
      setError(err.response?.data?.error || 'Failed to load market data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMarketOverview();

    // Auto-refresh every 5 minutes
    const interval = setInterval(() => {
      fetchMarketOverview(false);
    }, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online':
        return <CheckCircle color="success" fontSize="small" />;
      case 'offline':
        return <Warning color="warning" fontSize="small" />;
      case 'error':
        return <ErrorIcon color="error" fontSize="small" />;
      default:
        return <Info color="info" fontSize="small" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online':
        return 'success';
      case 'offline':
        return 'warning';
      case 'error':
        return 'error';
      default:
        return 'info';
    }
  };

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(price);
  };

  const formatChange = (change: number, percent: number) => {
    const sign = change >= 0 ? '+' : '';
    return `${sign}${change.toFixed(2)} (${sign}${percent.toFixed(2)}%)`;
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

  if (loading && !data) {
    return (
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="center" py={4}>
            <CircularProgress size={24} sx={{ mr: 2 }} />
            <Typography>Loading market data...</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (error && !data) {
    return (
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Alert
            severity="error"
            action={
              <IconButton
                color="inherit"
                size="small"
                onClick={() => fetchMarketOverview()}
              >
                <Refresh />
              </IconButton>
            }
          >
            {error}
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6" component="h2">
            Market Overview
          </Typography>
          <Box display="flex" alignItems="center" gap={1}>
            {data && (
              <Chip
                label={data.status === 'online' ? 'Live' : 'Offline'}
                color={data.status === 'online' ? 'success' : 'warning'}
                size="small"
                variant="outlined"
              />
            )}
            <Tooltip title={`Last updated: ${lastRefresh.toLocaleTimeString()}`}>
              <IconButton
                size="small"
                onClick={() => fetchMarketOverview()}
                disabled={loading}
              >
                <Refresh />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {error && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {/* Market Strength Indicator */}
        {data?.market_strength && (
          <Box mb={3}>
            <Typography variant="subtitle1" gutterBottom>
              Market Strength
            </Typography>
            <Box display="flex" alignItems="center" gap={2} mb={1}>
              <Chip
                label={`${data.market_strength.score}% - ${data.market_strength.level}`}
                color={getStrengthColor(data.market_strength.color) as any}
                size="small"
              />
              <Typography variant="body2" color="text.secondary">
                {data.market_strength.breakdown.bullish} Bullish • {data.market_strength.breakdown.neutral} Neutral • {data.market_strength.breakdown.bearish} Bearish
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={data.market_strength.score}
              color={getStrengthColor(data.market_strength.color) as any}
              sx={{ height: 8, borderRadius: 4 }}
            />
          </Box>
        )}

        {/* Market Instruments Grid */}
        <Grid container spacing={2}>
          {data?.instruments && Object.entries(data.instruments).map(([key, instrument]) => (
            <Grid item xs={12} sm={6} md={3} key={key}>
              <Card
                variant="outlined"
                sx={{
                  position: 'relative',
                  opacity: instrument.status === 'online' ? 1 : 0.7,
                }}
              >
                <CardContent sx={{ pb: '16px !important' }}>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1}>
                    <Box>
                      <Typography variant="h6" component="div" sx={{ fontSize: '1rem' }}>
                        {instrument.name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {instrument.symbol}
                      </Typography>
                    </Box>
                    <Tooltip title={`Status: ${instrument.status}`}>
                      {getStatusIcon(instrument.status)}
                    </Tooltip>
                  </Box>

                  {instrument.status === 'online' && instrument.current_price ? (
                    <>
                      <Typography variant="h5" component="div" sx={{ mb: 1 }}>
                        {formatPrice(instrument.current_price)}
                      </Typography>

                      {instrument.change !== undefined && instrument.change_percent !== undefined && (
                        <Box display="flex" alignItems="center">
                          {instrument.change >= 0 ? (
                            <TrendingUp color="success" fontSize="small" />
                          ) : (
                            <TrendingDown color="error" fontSize="small" />
                          )}
                          <Typography
                            variant="body2"
                            sx={{
                              ml: 0.5,
                              color: instrument.change >= 0 ? 'success.main' : 'error.main',
                              fontWeight: 'medium'
                            }}
                          >
                            {formatChange(instrument.change, instrument.change_percent)}
                          </Typography>
                        </Box>
                      )}
                    </>
                  ) : (
                    <Box>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        {instrument.error || 'Data unavailable'}
                      </Typography>
                      <Chip
                        label={instrument.status}
                        color={getStatusColor(instrument.status) as any}
                        size="small"
                        variant="outlined"
                      />
                    </Box>
                  )}

                  <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                    {instrument.last_updated ? new Date(instrument.last_updated).toLocaleTimeString() : 'No data'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>

        {data && (
          <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block', textAlign: 'center' }}>
            Last updated: {new Date(data.last_updated).toLocaleString()}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
};

export default MarketOverview;