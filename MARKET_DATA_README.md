# TradeSense AI - Market Data Integration

## Overview

TradeSense AI now includes professional market data integration using:

- **Yahoo Finance (yfinance)**: Real-time global market data
- **Casablanca Stock Exchange**: Moroccan market data via web scraping
- **Intelligent Fallbacks**: Automatic fallback to cached/mock data

## Features

### Yahoo Finance Integration
- ✅ Real-time stock prices for global markets
- ✅ Previous close prices and price changes
- ✅ Handles US, European, and Asian markets
- ✅ Rate limiting and error handling
- ✅ Automatic retries and caching

### Casablanca Stock Exchange Integration
- ✅ Web scraping using BeautifulSoup
- ✅ Multiple scraping strategies for robustness
- ✅ Moroccan dirham (MAD) price formatting
- ✅ Fallback to mock data when scraping fails
- ✅ Real-time price discovery

### Intelligent Data Management
- ✅ 5-minute price caching for performance
- ✅ Automatic fallback mechanisms
- ✅ Rate limiting to respect API limits
- ✅ Comprehensive error handling

## API Endpoints

### Get Market Prices
```http
GET /api/market/prices?symbols=AAPL,BCP.MA,MSFT
```

**Response:**
```json
{
  "prices": {
    "AAPL": {
      "current_price": 195.89,
      "previous_close": 193.42,
      "change": 2.47,
      "change_percent": 1.28,
      "source": "yahoo",
      "last_updated": "2026-01-18T15:00:00.000Z",
      "currency": "USD"
    },
    "BCP.MA": {
      "current_price": 285.00,
      "previous_close": 280.50,
      "change": 4.50,
      "change_percent": 1.60,
      "source": "casablanca",
      "last_updated": "2026-01-18T15:00:00.000Z",
      "currency": "MAD"
    }
  },
  "count": 2,
  "timestamp": "2026-01-18T15:00:00.000Z"
}
```

### Get Market Status
```http
GET /api/market/status
```

**Response:**
```json
{
  "markets": {
    "casablanca": {
      "open": true,
      "name": "Casablanca Stock Exchange",
      "timezone": "WET",
      "trading_hours": "09:30-15:30 WET",
      "last_updated": "2026-01-18T15:00:00.000Z"
    },
    "us": {
      "open": true,
      "name": "US Markets",
      "timezone": "EST",
      "trading_hours": "09:30-16:00 EST",
      "last_updated": "2026-01-18T15:00:00.000Z"
    }
  },
  "timestamp": "2026-01-18T15:00:00.000Z"
}
```

### Test Scraping Functionality
```http
GET /api/market/test-scraping
```

Returns test results for all data sources.

## Supported Symbols

### Global Markets (Yahoo Finance)
- `AAPL` - Apple Inc.
- `MSFT` - Microsoft Corporation
- `GOOGL` - Alphabet Inc.
- `TSLA` - Tesla Inc.
- And 10,000+ other global symbols

### Casablanca Stock Exchange (.MA suffix)
- `BCP.MA` - Banque Centrale Populaire
- `IAM.MA` - Itissalat Al-Maghrib
- `TQM.MA` - Total Quartz Maroc
- `LHM.MA` - LafargeHolcim Maroc
- `ATL.MA` - Atlantasanadir
- Plus 70+ Moroccan stocks

## Architecture

### Data Flow Priority
1. **Real Yahoo Finance Data** → Cache (5 min)
2. **Real Casablanca Scraping** → Cache (5 min)
3. **Mock Casablanca Data** → Fallback
4. **Error Handling** → Graceful degradation

### Rate Limiting
- Yahoo Finance: 1 request/second
- Casablanca: 1 request/second
- Automatic backoff on failures

### Caching Strategy
- Prices cached for 5 minutes
- Automatic cache invalidation
- Memory-efficient storage

## Usage in Frontend

```typescript
import { apiClient } from '../services/api';

// Get prices for multiple symbols
const prices = await apiClient.getMarketPrices(['AAPL', 'BCP.MA', 'MSFT']);

// Get market status
const status = await apiClient.getMarketStatus();

// Get detailed symbol info
const symbolInfo = await apiClient.getSymbolDetails('BCP.MA');
```

## Error Handling

The system gracefully handles:
- Network failures
- API rate limits
- Website structure changes
- Invalid symbols
- Temporary service outages

All errors are logged and fallback mechanisms ensure the system continues working.

## Production Considerations

### For Real Casablanca Data
1. **API Access**: Consider getting official API access from Casablanca bourse
2. **Legal Compliance**: Ensure compliance with terms of service
3. **Rate Limiting**: Implement appropriate delays between requests
4. **Error Monitoring**: Set up alerts for scraping failures

### For Yahoo Finance
1. **API Limits**: Monitor usage limits
2. **Alternative Sources**: Have backup data providers
3. **Data Quality**: Validate price data accuracy

### General
1. **Caching**: Implement Redis caching for production scale
2. **Monitoring**: Add metrics and alerting
3. **Fallbacks**: Multiple data source redundancy
4. **Security**: Secure API keys and credentials

## Testing

Test the market data integration:

```bash
# Test scraping functionality
curl http://localhost:8000/api/market/test-scraping

# Test price retrieval
curl "http://localhost:8000/api/market/prices?symbols=AAPL,BCP.MA"

# Test market status
curl http://localhost:8000/api/market/status
```

## Future Enhancements

- Real-time WebSocket price feeds
- Historical price data
- Technical indicators calculation
- Multi-exchange support
- Advanced caching strategies
- Machine learning price predictions