/* eslint-disable react-hooks/exhaustive-deps */
import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Grid,
  Alert,
  CircularProgress,
  Button,
  TextField,
  InputAdornment,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Search as SearchIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';

import { apiClient } from '../../services/api';

interface MarketPrice {
  current_price: number;
  previous_close?: number;
  change: number;
  change_percent: number;
  source: string;
  last_updated: string;
  currency: string;
  error?: string;
}

const MarketDataWidget: React.FC = () => {
  const [marketData, setMarketData] = useState<Record<string, MarketPrice>>({});
  const [marketStatus, setMarketStatus] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchSymbol, setSearchSymbol] = useState('');
  const [customSymbols, setCustomSymbols] = useState<string[]>([]);

  const defaultSymbols = ['AAPL', 'BCP.MA', 'MSFT', 'IAM.MA', 'TSLA'];

  // We intentionally load once on mount; dependencies are stable
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    loadMarketData();
    loadMarketStatus();
  }, []);

  const loadMarketData = async (symbols: string[] = defaultSymbols) => {
    try {
      setLoading(true);
      const response = await apiClient.getMarketPrices(symbols);
      setMarketData(response.data.prices);
      setError('');
    } catch (err) {
      setError('Failed to load market data');
      console.error('Error loading market data:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadMarketStatus = async () => {
    try {
      const response = await apiClient.getMarketStatus();
      setMarketStatus(response.data.markets);
    } catch (err) {
      console.error('Error loading market status:', err);
    }
  };

  const handleSearchSymbol = async () => {
    if (!searchSymbol.trim()) return;

    const symbol = searchSymbol.trim().toUpperCase();
    try {
      const response = await apiClient.getSymbolDetails(symbol);
      setMarketData(prev => ({
        ...prev,
        [symbol]: response.data
      }));
      setCustomSymbols(prev => [...prev, symbol]);
      setSearchSymbol('');
    } catch (err) {
      setError(`Symbol ${symbol} not found`);
      console.error('Error searching symbol:', err);
    }
  };

  const handleRefresh = () => {
    const allSymbols = [...defaultSymbols, ...customSymbols];
    loadMarketData(allSymbols);
    loadMarketStatus();
  };

  const formatPrice = (price: number, currency: string) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency === 'MAD' ? 'MAD' : 'USD',
      minimumFractionDigits: 2,
    }).format(price);
  };

  const getPriceColor = (change: number) => {
    return change >= 0 ? 'success.main' : 'error.main';
  };

  const getChangeIcon = (change: number) => {
    return change >= 0 ? <TrendingUpIcon /> : <TrendingDownIcon />;
  };

  return (
    <Card>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h6">
            Live Market Data
          </Typography>
          <Box display="flex" gap={1}>
            {marketStatus.casablanca && (
              <Chip
                label={`Casablanca: ${marketStatus.casablanca.open ? 'Open' : 'Closed'}`}
                color={marketStatus.casablanca.open ? 'success' : 'default'}
                size="small"
              />
            )}
            <Button
              size="small"
              startIcon={<RefreshIcon />}
              onClick={handleRefresh}
              disabled={loading}
            >
              Refresh
            </Button>
          </Box>
        </Box>

        {/* Symbol Search */}
        <Box display="flex" gap={1} mb={3}>
          <TextField
            size="small"
            placeholder="Search symbol (e.g., AAPL, BCP.MA)"
            value={searchSymbol}
            onChange={(e) => setSearchSymbol(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearchSymbol()}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
            sx={{ flex: 1 }}
          />
          <Button
            variant="contained"
            onClick={handleSearchSymbol}
            disabled={!searchSymbol.trim() || loading}
          >
            Add
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {loading ? (
          <Box display="flex" justifyContent="center" alignItems="center" py={4}>
            <CircularProgress />
          </Box>
        ) : (
          <Grid container spacing={2}>
            {Object.entries(marketData).map(([symbol, data]) => {
              if (data.error) {
                return (
                  <Grid item xs={12} sm={6} md={4} key={symbol}>
                    <Card variant="outlined" sx={{ p: 2 }}>
                      <Typography variant="h6" color="error">
                        {symbol}
                      </Typography>
                      <Typography variant="body2" color="error">
                        {data.error}
                      </Typography>
                    </Card>
                  </Grid>
                );
              }

              return (
                <Grid item xs={12} sm={6} md={4} key={symbol}>
                  <Card variant="outlined" sx={{ p: 2 }}>
                    <Box display="flex" justifyContent="space-between" alignItems="start" mb={1}>
                      <Typography variant="h6">
                        {symbol}
                      </Typography>
                      <Chip
                        label={data.source}
                        size="small"
                        color="primary"
                        variant="outlined"
                      />
                    </Box>

                    <Typography variant="h4" sx={{ mb: 1 }}>
                      {formatPrice(data.current_price, data.currency)}
                    </Typography>

                    {data.previous_close && (
                      <Box display="flex" alignItems="center" gap={1}>
                        {getChangeIcon(data.change)}
                        <Typography
                          variant="body2"
                          sx={{ color: getPriceColor(data.change) }}
                        >
                          {data.change >= 0 ? '+' : ''}{formatPrice(data.change, data.currency)}
                          ({data.change_percent >= 0 ? '+' : ''}{data.change_percent.toFixed(2)}%)
                        </Typography>
                      </Box>
                    )}

                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                      Updated: {new Date(data.last_updated).toLocaleTimeString()}
                    </Typography>
                  </Card>
                </Grid>
              );
            })}
          </Grid>
        )}

        <Alert severity="info" sx={{ mt: 3 }}>
          <Typography variant="body2">
            <strong>Data Sources:</strong> Yahoo Finance for global markets,
            Casablanca Stock Exchange web scraping for Moroccan stocks (.MA).
            Prices update every 5 minutes with automatic caching.
          </Typography>
        </Alert>
      </CardContent>
    </Card>
  );
};

export default MarketDataWidget;