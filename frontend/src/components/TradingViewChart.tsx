/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useRef, useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Chip,
} from '@mui/material';
import {
  Refresh,
  Fullscreen,
  Timeline,
  VolumeUp,
} from '@mui/icons-material';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  ColorType,
  CrosshairMode,
} from 'lightweight-charts';
import { apiClient } from '../services/api';

interface ChartDataPoint {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface TradingViewChartProps {
  symbol?: string;
  height?: number;
  showVolume?: boolean;
  autoRefresh?: boolean;
}

const SYMBOLS = [
  { value: '^GSPC', label: 'S&P 500 (SPX)', category: 'Index' },
  { value: '^IXIC', label: 'NASDAQ (IXIC)', category: 'Index' },
  { value: '^DJI', label: 'Dow Jones (DJI)', category: 'Index' },
  { value: 'GC=F', label: 'Gold Futures (GC=F)', category: 'Commodity' },
  { value: 'AAPL', label: 'Apple (AAPL)', category: 'Stock' },
  { value: 'MSFT', label: 'Microsoft (MSFT)', category: 'Stock' },
  { value: 'GOOGL', label: 'Alphabet (GOOGL)', category: 'Stock' },
  { value: 'AMZN', label: 'Amazon (AMZN)', category: 'Stock' },
  { value: 'TSLA', label: 'Tesla (TSLA)', category: 'Stock' },
];

const TIMEFRAMES = [
  { value: '1d', label: '1 Day', interval: '5m' },
  { value: '5d', label: '5 Days', interval: '15m' },
  { value: '1mo', label: '1 Month', interval: '1h' },
  { value: '3mo', label: '3 Months', interval: '1d' },
  { value: '6mo', label: '6 Months', interval: '1d' },
  { value: '1y', label: '1 Year', interval: '1d' },
  { value: '2y', label: '2 Years', interval: '1wk' },
  { value: '5y', label: '5 Years', interval: '1wk' },
];

const TradingViewChart: React.FC<TradingViewChartProps> = ({
  symbol: initialSymbol = '^GSPC',
  height = 400,
  showVolume = true,
  autoRefresh = true,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  const [selectedSymbol, setSelectedSymbol] = useState(initialSymbol);
  const [selectedTimeframe, setSelectedTimeframe] = useState('1mo');
  const [chartData, setChartData] = useState<ChartDataPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const fetchChartData = async (symbol: string, period: string) => {
    setLoading(true);
    setError(null);

    try {
      // Find the appropriate interval for the period
      const timeframeConfig = TIMEFRAMES.find(tf => tf.value === period);
      const interval = timeframeConfig?.interval || '1d';

      const response = await apiClient.getChartData(symbol, period, interval);

      if (response.data.success && response.data.data) {
        setChartData(response.data.data);
        setLastUpdate(new Date(response.data.last_updated));
      } else {
        setError(response.data.error || 'Failed to load chart data');
      }
    } catch (err: any) {
      console.error('Failed to fetch chart data:', err);
      setError(err.response?.data?.error || 'Failed to load chart data');
    } finally {
      setLoading(false);
    }
  };

  const initializeChart = () => {
    if (!chartContainerRef.current) return;

    // Clean up existing chart
    if (chartRef.current) {
      chartRef.current.remove();
    }

    // Create new chart
    // Cast to any to avoid TS type mismatches across lightweight-charts versions
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#ffffff' },
        textColor: '#333333',
      },
      grid: {
        vertLines: { color: '#e1e1e1' },
        horzLines: { color: '#e1e1e1' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: '#cccccc',
      },
      timeScale: {
        borderColor: '#cccccc',
        timeVisible: true,
        secondsVisible: false,
      },
      width: chartContainerRef.current.clientWidth,
      height: height,
    }) as any;

    chartRef.current = chart;

    // Create candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    });

    candlestickSeriesRef.current = candlestickSeries;

    // Create volume series if enabled
    if (showVolume) {
      const volumeSeries = chart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: '',
      });

      volumeSeriesRef.current = volumeSeries;

      // Set up price scale for volume
      chart.priceScale('').applyOptions({
        scaleMargins: {
          top: 0.7,
          bottom: 0,
        },
      });
    }

    // Fit content when data is loaded
    chart.timeScale().fitContent();

    return chart;
  };

  const updateChartData = () => {
    if (!candlestickSeriesRef.current) return;

    if (chartData.length === 0) return;

    // Convert data to candlestick format
    const candlestickData: CandlestickData[] = chartData.map(point => ({
      time: point.time as any,
      open: point.open,
      high: point.high,
      low: point.low,
      close: point.close,
    }));

    // Set candlestick data
    candlestickSeriesRef.current.setData(candlestickData);

    // Set volume data if enabled
    if (showVolume && volumeSeriesRef.current) {
      const volumeData: any[] = chartData.map(point => ({
        time: point.time as any,
        value: point.volume,
        color: point.close >= point.open ? '#26a69a' : '#ef5350',
      }));

      volumeSeriesRef.current.setData(volumeData);
    }

    // Fit content to show all data
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  };

  const handleSymbolChange = (newSymbol: string) => {
    setSelectedSymbol(newSymbol);
    fetchChartData(newSymbol, selectedTimeframe);
  };

  const handleTimeframeChange = (newTimeframe: string) => {
    setSelectedTimeframe(newTimeframe);
    fetchChartData(selectedSymbol, newTimeframe);
  };

  const handleRefresh = () => {
    fetchChartData(selectedSymbol, selectedTimeframe);
  };

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  // Initialize chart on mount
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const chart = initializeChart();
    return () => {
      if (chart) {
        chart.remove();
      }
    };
  }, [isFullscreen]);

  // Update chart data when data changes
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    updateChartData();
  }, [chartData]);

  // Fetch data on mount and when symbol/timeframe changes
  useEffect(() => {
    fetchChartData(selectedSymbol, selectedTimeframe);
  }, [selectedSymbol, selectedTimeframe]);

  // Auto-refresh every 5 minutes
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchChartData(selectedSymbol, selectedTimeframe);
    }, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, [selectedSymbol, selectedTimeframe, autoRefresh]);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (chartRef.current && chartContainerRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const selectedSymbolInfo = SYMBOLS.find(s => s.value === selectedSymbol);

  return (
    <Card sx={{ mb: 3, ...(isFullscreen && { position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999, m: 0 }) }}>
      <CardContent>
        {/* Chart Header */}
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2} flexWrap="wrap" gap={1}>
          <Box display="flex" alignItems="center" gap={1}>
            <Timeline color="primary" />
            <Typography variant="h6" component="h2">
              Price Chart
            </Typography>
            {selectedSymbolInfo && (
              <Chip
                label={`${selectedSymbolInfo.label} (${selectedSymbolInfo.category})`}
                size="small"
                color="primary"
                variant="outlined"
              />
            )}
          </Box>

          <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
            {/* Symbol Selector */}
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Symbol</InputLabel>
              <Select
                value={selectedSymbol}
                label="Symbol"
                onChange={(e) => handleSymbolChange(e.target.value)}
              >
                {SYMBOLS.map((symbol) => (
                  <MenuItem key={symbol.value} value={symbol.value}>
                    {symbol.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Timeframe Selector */}
            <FormControl size="small" sx={{ minWidth: 100 }}>
              <InputLabel>Timeframe</InputLabel>
              <Select
                value={selectedTimeframe}
                label="Timeframe"
                onChange={(e) => handleTimeframeChange(e.target.value)}
              >
                {TIMEFRAMES.map((tf) => (
                  <MenuItem key={tf.value} value={tf.value}>
                    {tf.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Action Buttons */}
            <Tooltip title="Refresh Data">
              <IconButton onClick={handleRefresh} disabled={loading}>
                <Refresh />
              </IconButton>
            </Tooltip>

            <Tooltip title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}>
              <IconButton onClick={toggleFullscreen}>
                <Fullscreen />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Loading/Error States */}
        {loading && (
          <Box display="flex" alignItems="center" justifyContent="center" py={4}>
            <CircularProgress size={24} sx={{ mr: 2 }} />
            <Typography>Loading chart data...</Typography>
          </Box>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {/* Chart Status */}
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
          <Typography variant="body2" color="text.secondary">
            {chartData.length} data points loaded
          </Typography>

          {lastUpdate && (
            <Typography variant="body2" color="text.secondary">
              Last update: {lastUpdate.toLocaleTimeString()}
            </Typography>
          )}
        </Box>

        {/* Chart Container */}
        <Box
          ref={chartContainerRef}
          sx={{
            width: '100%',
            height: isFullscreen ? 'calc(100vh - 200px)' : height,
            border: '1px solid #e0e0e0',
            borderRadius: 1,
            position: 'relative',
            '& canvas': {
              cursor: 'crosshair',
            },
          }}
        />

        {/* Chart Legend */}
        <Box display="flex" justifyContent="center" gap={2} mt={1}>
          <Box display="flex" alignItems="center" gap={0.5}>
            <Box sx={{ width: 12, height: 12, backgroundColor: '#26a69a', borderRadius: 0.5 }} />
            <Typography variant="caption">Bullish</Typography>
          </Box>
          <Box display="flex" alignItems="center" gap={0.5}>
            <Box sx={{ width: 12, height: 12, backgroundColor: '#ef5350', borderRadius: 0.5 }} />
            <Typography variant="caption">Bearish</Typography>
          </Box>
          {showVolume && (
            <Box display="flex" alignItems="center" gap={0.5}>
              <VolumeUp fontSize="small" color="action" />
              <Typography variant="caption">Volume</Typography>
            </Box>
          )}
        </Box>
      </CardContent>
    </Card>
  );
};

export default TradingViewChart;