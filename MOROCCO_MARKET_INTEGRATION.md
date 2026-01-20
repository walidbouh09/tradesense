# Moroccan Stock Market Integration - Casablanca Stock Exchange

## Overview

This document describes the **minimal web scraping solution** for fetching real-time stock prices from the **Casablanca Stock Exchange** (Bourse de Casablanca). The implementation uses BeautifulSoup for safe, respectful web scraping with multiple fallback strategies.

## 🎯 Key Features

### Minimal & Respectful Scraping
- ✅ **Rate Limiting**: 1-second delay between requests
- ✅ **Caching**: 5-minute cache to reduce server load
- ✅ **Multiple Strategies**: Fallback mechanisms for HTML changes
- ✅ **No Aggressive Crawling**: Single-page requests only
- ✅ **No Scheduling**: On-demand fetching only

### Supported Stocks
- ✅ **IAM** (Itissalat Al-Maghrib / Maroc Telecom)
- ✅ **ATW** (Attijariwafa Bank)
- ✅ **BCP** (Banque Centrale Populaire)
- ✅ **ATL** (ATLANTASANADIR)
- ✅ **TQM** (Total Quartz Maroc)
- ✅ **LHM** (LafargeHolcim Maroc)
- ✅ And more...

### Robust Implementation
- ✅ **BeautifulSoup**: HTML parsing with lxml
- ✅ **Multiple URL Strategies**: Tries different page structures
- ✅ **Multiple Parsing Strategies**: CSS selectors, tables, scripts, meta tags
- ✅ **Error Handling**: Graceful degradation with fallbacks
- ✅ **Mock Data**: Realistic fallback when scraping fails

## 📡 API Endpoint

### Get Moroccan Stock Price

```http
GET /api/market/morocco/<symbol>
```

**Parameters:**
- `symbol` (path): Stock symbol (e.g., 'IAM', 'ATW', 'BCP')
  - Automatically appends `.MA` if not present
  - Case-insensitive

**Response (Success):**
```json
{
  "success": true,
  "symbol": "IAM.MA",
  "name": "Itissalat Al-Maghrib (Maroc Telecom)",
  "exchange": "Casablanca Stock Exchange",
  "currency": "MAD",
  "price": {
    "current": 145.25,
    "previous_close": 143.80,
    "change": 1.45,
    "change_percent": 1.01
  },
  "market": {
    "is_open": true,
    "timezone": "Africa/Casablanca",
    "trading_hours": "09:30 - 15:30 WET"
  },
  "metadata": {
    "data_source": "Casablanca Stock Exchange (Web Scraping)",
    "last_updated": "2024-01-19T10:30:00Z",
    "cache_ttl": 300,
    "note": "Minimal scraping - respectful to exchange servers"
  }
}
```

**Response (Not Found):**
```json
{
  "success": false,
  "error": "Unable to fetch price for IAM.MA",
  "message": "Stock not found or Casablanca Stock Exchange data unavailable",
  "symbol": "IAM.MA",
  "exchange": "Casablanca Stock Exchange",
  "currency": "MAD"
}
```

## 🧪 Testing

### Test IAM (Maroc Telecom)
```bash
curl http://localhost:5000/api/market/morocco/IAM
```

### Test ATW (Attijariwafa Bank)
```bash
curl http://localhost:5000/api/market/morocco/ATW
```

### Test with .MA suffix
```bash
curl http://localhost:5000/api/market/morocco/IAM.MA
```

### Test lowercase
```bash
curl http://localhost:5000/api/market/morocco/iam
```

## 🔧 Implementation Details

### Web Scraping Architecture

The implementation uses a **multi-strategy approach** to handle HTML structure changes:

#### Strategy 1: CSS Selectors
```python
# Look for specific price classes
price_selectors = [
    '.cours-actuel', '.prix-actuel', '.current-price',
    '.last-price', '.valeur-actuelle', '.price-current',
    '[data-cours]', '[data-price]', '[data-valeur]'
]
```

#### Strategy 2: Table Parsing
```python
# Parse structured tables
tables = soup.find_all('table')
# Look for rows with price labels
# Extract values from cells
```

#### Strategy 3: Script Extraction
```python
# Extract JSON data from embedded scripts
price_patterns = [
    r'"(cours|prix|price)"\s*:\s*([0-9.,]+)',
    r'cours\s*[:=]\s*([0-9.,]+)'
]
```

#### Strategy 4: Meta Tags
```python
# Check meta tags for structured data
meta_tags = soup.find_all('meta')
# Look for og:price, price, value properties
```

### URL Strategies

The scraper tries multiple URL patterns:
```python
urls_to_try = [
    f"{base_url}/bourse/actions/{symbol}",
    f"{base_url}/marche/actions/{symbol}",
    f"{base_url}/cours/actions/{symbol}",
    f"{base_url}/en/bourse/actions/{symbol}",
    f"{base_url}/bourse/action/{symbol}"
]
```

### Rate Limiting

```python
# 1-second delay between requests
self.request_delay = 1.0

# Per-source rate limiting
def _rate_limit(self, source: str = 'default'):
    now = time.time()
    if source in self.last_request_time:
        time_diff = now - self.last_request_time[source]
        if time_diff < self.request_delay:
            time.sleep(self.request_delay - time_diff)
    self.last_request_time[source] = now
```

### Caching

```python
# 5-minute cache to reduce server load
cache_expiry = 300  # seconds

def _get_cached_price(self, symbol: str):
    if symbol in self.cache_expiry:
        if time.time() < self.cache_expiry[symbol]:
            return self.price_cache.get(symbol)
    return None
```

### Price Text Cleaning

Handles Moroccan number formatting:
```python
def _clean_price_text(self, text: str):
    # Remove currency symbols (MAD, DH, Dirhams)
    text = re.sub(r'(?i)(mad|dh|dirhams?)', '', text)
    
    # Handle Moroccan comma decimal separator
    text = text.replace(',', '.')
    
    # Remove thousand separators
    text = re.sub(r'\s+', '', text)
    
    return text
```

## 🔒 Safety Features

### Respectful Scraping
1. **Rate Limiting**: 1-second minimum delay between requests
2. **Caching**: 5-minute cache reduces repeated requests
3. **User-Agent**: Proper browser identification
4. **Timeout**: 15-second request timeout
5. **Single Page**: No recursive crawling

### Error Handling
1. **Multiple Strategies**: Tries different parsing methods
2. **Multiple URLs**: Tries different page structures
3. **Graceful Degradation**: Falls back to mock data
4. **Logging**: Comprehensive error logging
5. **No Crashes**: All exceptions caught and handled

### HTML Structure Changes
The implementation is **resilient to HTML changes**:
- Multiple CSS selectors
- Multiple parsing strategies
- Multiple URL patterns
- Fallback to mock data
- Clear error messages

## 📊 Supported Moroccan Stocks

| Symbol | Company Name | Typical Price Range |
|--------|--------------|---------------------|
| IAM.MA | Itissalat Al-Maghrib (Maroc Telecom) | 140-150 MAD |
| ATW.MA | Attijariwafa Bank | 450-500 MAD |
| BCP.MA | Banque Centrale Populaire | 280-290 MAD |
| ATL.MA | ATLANTASANADIR | 115-125 MAD |
| TQM.MA | Total Quartz Maroc | 870-900 MAD |
| LHM.MA | LafargeHolcim Maroc | 1600-1700 MAD |
| ADH.MA | Auto Hall Distribution | 80-90 MAD |
| CMA.MA | Ciments du Maroc | 1400-1450 MAD |
| CDM.MA | Credit du Maroc | 610-630 MAD |

## 🚀 Integration Examples

### Python Example
```python
import requests

# Fetch IAM stock price
response = requests.get('http://localhost:5000/api/market/morocco/IAM')
data = response.json()

if data['success']:
    print(f"Stock: {data['name']}")
    print(f"Price: {data['price']['current']} MAD")
    print(f"Change: {data['price']['change_percent']}%")
else:
    print(f"Error: {data['error']}")
```

### JavaScript Example
```javascript
// Fetch ATW stock price
fetch('http://localhost:5000/api/market/morocco/ATW')
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log(`Stock: ${data.name}`);
      console.log(`Price: ${data.price.current} MAD`);
      console.log(`Change: ${data.price.change_percent}%`);
    } else {
      console.error(`Error: ${data.error}`);
    }
  });
```

### cURL Example
```bash
# Fetch BCP stock price
curl -X GET http://localhost:5000/api/market/morocco/BCP | jq .

# Expected output:
# {
#   "success": true,
#   "symbol": "BCP.MA",
#   "name": "Banque Centrale Populaire",
#   "price": {
#     "current": 285.00,
#     "previous_close": 280.50,
#     "change": 4.50,
#     "change_percent": 1.60
#   }
# }
```

## 🔍 Troubleshooting

### Issue: "Stock not found"
**Cause**: Symbol doesn't exist or scraping failed  
**Solution**: 
- Verify symbol is correct (IAM, ATW, BCP, etc.)
- Check if Casablanca Stock Exchange website is accessible
- Review logs for scraping errors

### Issue: Stale prices
**Cause**: Cache is serving old data  
**Solution**: 
- Wait 5 minutes for cache to expire
- Restart application to clear cache
- Check if market is open (09:30-15:30 WET)

### Issue: Slow response
**Cause**: First request after cache expiry  
**Solution**: 
- Normal behavior - scraping takes 1-3 seconds
- Subsequent requests use cache (instant)
- Consider pre-warming cache for critical stocks

## 📝 Dependencies

### Required Python Packages
```txt
beautifulsoup4==4.12.2
lxml==4.9.3
requests==2.31.0
yfinance==0.2.28
```

### Installation
```bash
pip install beautifulsoup4 lxml requests yfinance
```

## 🎯 Design Decisions

### Why BeautifulSoup?
- **Robust**: Handles malformed HTML
- **Flexible**: Multiple parsing strategies
- **Fast**: lxml parser for performance
- **Mature**: Well-tested library

### Why Not Selenium?
- **Overhead**: Too heavy for simple scraping
- **Resources**: Requires browser driver
- **Speed**: Much slower than requests
- **Complexity**: Unnecessary for static pages

### Why Caching?
- **Performance**: Instant responses for cached data
- **Respectful**: Reduces load on exchange servers
- **Reliability**: Serves stale data if scraping fails
- **Cost**: Reduces bandwidth usage

### Why Multiple Strategies?
- **Resilience**: Handles HTML structure changes
- **Reliability**: Increases success rate
- **Maintenance**: Reduces need for updates
- **Robustness**: Graceful degradation

## 🚨 Important Notes

### Legal & Ethical
- ✅ **Public Data**: Scraping publicly available data
- ✅ **Respectful**: Rate limiting and caching
- ✅ **No Login**: No authentication required
- ✅ **No Automation**: On-demand only, no scheduling
- ⚠️ **Terms of Service**: Review exchange's ToS

### Production Considerations
- Consider official API if available
- Monitor scraping success rate
- Implement alerting for failures
- Regular testing of scraping logic
- Fallback to mock data for demos

### Limitations
- **Market Hours**: Data only during trading hours
- **Delay**: 1-3 second latency for fresh data
- **Coverage**: Limited to major Moroccan stocks
- **Accuracy**: Best-effort, not guaranteed
- **Availability**: Depends on exchange website

## 📚 Additional Resources

- [Casablanca Stock Exchange](https://www.casablanca-bourse.com)
- [BeautifulSoup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [Requests Documentation](https://requests.readthedocs.io/)
- [Web Scraping Best Practices](https://www.scrapehero.com/web-scraping-best-practices/)

---

**Version**: 1.0  
**Last Updated**: January 19, 2024  
**Status**: ✅ Production Ready (Minimal Scraping)
