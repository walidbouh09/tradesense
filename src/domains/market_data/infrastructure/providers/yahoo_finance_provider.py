"""Yahoo Finance market data provider implementation."""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode
import json

import structlog

from ...domain.entities import Symbol, MarketDataPoint, OHLCV, OrderBook, Trade
from ...domain.value_objects import TimeFrame, DataQuality
from .base_provider import BaseMarketDataProvider, ProviderFactory

logger = structlog.get_logger()


class YahooFinanceProvider(BaseMarketDataProvider):
    """Yahoo Finance market data provider."""
    
    def __init__(self, provider_config: Dict[str, Any], session=None):
        super().__init__(provider_config, session)
        self.base_url = "https://query1.finance.yahoo.com"
        
        # Yahoo Finance specific configuration
        self.supported_markets = ["US", "GLOBAL", "MOROCCO"]
        self.supported_data_types = [
            "quote", "chart", "history", "options", "fundamentals",
            "news", "statistics", "profile", "financials"
        ]
        
        # Timeframe mapping for Yahoo Finance
        self.interval_mapping = {
            TimeFrame.MINUTE_1: "1m",
            TimeFrame.MINUTE_2: "2m",
            TimeFrame.MINUTE_5: "5m",
            TimeFrame.MINUTE_15: "15m",
            TimeFrame.MINUTE_30: "30m",
            TimeFrame.MINUTE_60: "60m",
            TimeFrame.MINUTE_90: "90m",
            TimeFrame.HOUR_1: "1h",
            TimeFrame.DAY_1: "1d",
            TimeFrame.WEEK_1: "1wk",
            TimeFrame.MONTH_1: "1mo",
        }
        
        # Period mapping
        self.period_mapping = {
            "1d": ["1m", "2m", "5m", "15m", "30m", "60m", "90m"],
            "5d": ["1m", "2m", "5m", "15m", "30m", "60m", "90m"],
            "1mo": ["30m", "60m", "90m", "1h", "1d"],
            "3mo": ["1d", "5d", "1wk", "1mo"],
            "6mo": ["1d", "5d", "1wk", "1mo"],
            "1y": ["1d", "5d", "1wk", "1mo"],
            "2y": ["1d", "5d", "1wk", "1mo"],
            "5y": ["1d", "5d", "1wk", "1mo"],
            "10y": ["1d", "5d", "1wk", "1mo"],
            "ytd": ["1d", "5d", "1wk", "1mo"],
            "max": ["1d", "5d", "1wk", "1mo"],
        }
    
    async def get_real_time_quote(self, symbol: Symbol) -> Optional[MarketDataPoint]:
        """Get real-time quote for symbol."""
        try:
            yahoo_symbol = self._normalize_symbol(symbol)
            
            # Use Yahoo Finance v8 API
            url = f"{self.base_url}/v8/finance/chart/{yahoo_symbol}"
            params = {
                "interval": "1m",
                "range": "1d",
                "includePrePost": "true",
            }
            
            response = await self._make_request("GET", url, params=params)
            
            if "chart" not in response or not response["chart"]["result"]:
                logger.warning(
                    "No data in Yahoo Finance response",
                    symbol=yahoo_symbol,
                    response_keys=list(response.keys()) if response else [],
                )
                return None
            
            chart_data = response["chart"]["result"][0]
            meta = chart_data.get("meta", {})
            
            # Get the latest price
            current_price = meta.get("regularMarketPrice")
            if current_price is None:
                current_price = meta.get("previousClose")
            
            if current_price is None:
                logger.warning("No price data available", symbol=yahoo_symbol)
                return None
            
            # Get timestamp
            market_time = meta.get("regularMarketTime")
            if market_time:
                timestamp = datetime.fromtimestamp(market_time)
            else:
                timestamp = datetime.utcnow()
            
            return MarketDataPoint(
                symbol=symbol,
                timestamp=timestamp,
                price=Decimal(str(current_price)),
                volume=Decimal(str(meta.get("regularMarketVolume", 0))),
                bid=Decimal(str(meta.get("bid", 0))) if meta.get("bid") else None,
                ask=Decimal(str(meta.get("ask", 0))) if meta.get("ask") else None,
                bid_size=Decimal(str(meta.get("bidSize", 0))) if meta.get("bidSize") else None,
                ask_size=Decimal(str(meta.get("askSize", 0))) if meta.get("askSize") else None,
                provider=self.name,
                quality=DataQuality.DELAYED,  # Yahoo Finance is typically delayed
                metadata={
                    "previous_close": meta.get("previousClose"),
                    "day_high": meta.get("regularMarketDayHigh"),
                    "day_low": meta.get("regularMarketDayLow"),
                    "day_range": meta.get("regularMarketDayRange"),
                    "fifty_two_week_high": meta.get("fiftyTwoWeekHigh"),
                    "fifty_two_week_low": meta.get("fiftyTwoWeekLow"),
                    "market_cap": meta.get("marketCap"),
                    "shares_outstanding": meta.get("sharesOutstanding"),
                    "currency": meta.get("currency"),
                    "exchange_name": meta.get("exchangeName"),
                    "instrument_type": meta.get("instrumentType"),
                }
            )
        
        except Exception as e:
            logger.error(
                "Failed to get real-time quote from Yahoo Finance",
                symbol=symbol.ticker,
                error=str(e),
            )
            return None
    
    async def get_historical_ohlcv(
        self,
        symbol: Symbol,
        start_time: datetime,
        end_time: datetime,
        timeframe: TimeFrame,
    ) -> List[OHLCV]:
        """Get historical OHLCV data."""
        try:
            yahoo_symbol = self._normalize_symbol(symbol)
            interval = self.interval_mapping.get(timeframe, "1d")
            
            # Convert datetime to Unix timestamp
            period1 = int(start_time.timestamp())
            period2 = int(end_time.timestamp())
            
            url = f"{self.base_url}/v8/finance/chart/{yahoo_symbol}"
            params = {
                "period1": period1,
                "period2": period2,
                "interval": interval,
                "includePrePost": "false",
                "events": "div,splits",
            }
            
            response = await self._make_request("GET", url, params=params)
            
            if "chart" not in response or not response["chart"]["result"]:
                logger.warning(
                    "No historical data in Yahoo Finance response",
                    symbol=yahoo_symbol,
                )
                return []
            
            chart_data = response["chart"]["result"][0]
            
            # Extract OHLCV data
            timestamps = chart_data.get("timestamp", [])
            indicators = chart_data.get("indicators", {})
            quote = indicators.get("quote", [{}])[0] if indicators.get("quote") else {}
            
            opens = quote.get("open", [])
            highs = quote.get("high", [])
            lows = quote.get("low", [])
            closes = quote.get("close", [])
            volumes = quote.get("volume", [])
            
            ohlcv_list = []
            
            for i, timestamp in enumerate(timestamps):
                # Skip if any required data is missing
                if (i >= len(opens) or i >= len(highs) or i >= len(lows) or 
                    i >= len(closes) or opens[i] is None or highs[i] is None or 
                    lows[i] is None or closes[i] is None):
                    continue
                
                dt = datetime.fromtimestamp(timestamp)
                volume = volumes[i] if i < len(volumes) and volumes[i] is not None else 0
                
                ohlcv = OHLCV(
                    symbol=symbol,
                    timestamp=dt,
                    open_price=Decimal(str(opens[i])),
                    high_price=Decimal(str(highs[i])),
                    low_price=Decimal(str(lows[i])),
                    close_price=Decimal(str(closes[i])),
                    volume=Decimal(str(volume)),
                    timeframe=timeframe.value,
                    provider=self.name,
                )
                
                ohlcv_list.append(ohlcv)
            
            return ohlcv_list
        
        except Exception as e:
            logger.error(
                "Failed to get historical OHLCV from Yahoo Finance",
                symbol=symbol.ticker,
                timeframe=timeframe,
                error=str(e),
            )
            return []
    
    async def get_order_book(self, symbol: Symbol, depth: int = 10) -> Optional[OrderBook]:
        """Get order book data."""
        # Yahoo Finance doesn't provide detailed order book data
        logger.warning(
            "Order book data not available from Yahoo Finance",
            symbol=symbol.ticker,
        )
        return None
    
    async def get_recent_trades(self, symbol: Symbol, limit: int = 100) -> List[Trade]:
        """Get recent trades."""
        # Yahoo Finance doesn't provide individual trade data
        logger.warning(
            "Individual trade data not available from Yahoo Finance",
            symbol=symbol.ticker,
        )
        return []
    
    def supports_symbol(self, symbol: Symbol) -> bool:
        """Check if provider supports the symbol."""
        # Yahoo Finance supports a wide range of global markets
        supported_exchanges = [
            # US Markets
            "NYSE", "NASDAQ", "AMEX", "OTC",
            # International Markets
            "LSE", "TSE", "FRA", "AMS", "SWX", "BOM", "NSE", "HKG", "TYO",
            # Moroccan Market
            "CSE", "CASABLANCA",
        ]
        
        return symbol.exchange in supported_exchanges
    
    def supports_data_type(self, data_type: str) -> bool:
        """Check if provider supports the data type."""
        return data_type.lower() in [dt.lower() for dt in self.supported_data_types]
    
    def get_supported_timeframes(self) -> List[TimeFrame]:
        """Get supported timeframes."""
        return list(self.interval_mapping.keys())
    
    async def _test_connection(self) -> bool:
        """Test connection to Yahoo Finance API."""
        try:
            # Test with a well-known symbol
            url = f"{self.base_url}/v8/finance/chart/AAPL"
            params = {"interval": "1d", "range": "1d"}
            
            response = await self._make_request("GET", url, params=params)
            
            # Check if we got a valid response
            return "chart" in response and response["chart"]["result"]
        
        except Exception as e:
            logger.error("Yahoo Finance connection test failed", error=str(e))
            return False
    
    def _normalize_symbol(self, symbol: Symbol) -> str:
        """Normalize symbol for Yahoo Finance."""
        # Yahoo Finance symbol format varies by exchange
        if symbol.is_us_market:
            return symbol.ticker
        
        # International markets often need exchange suffix
        exchange_suffixes = {
            "LSE": ".L",      # London Stock Exchange
            "TSE": ".TO",     # Toronto Stock Exchange
            "FRA": ".F",      # Frankfurt Stock Exchange
            "AMS": ".AS",     # Amsterdam Stock Exchange
            "SWX": ".SW",     # Swiss Exchange
            "BOM": ".BO",     # Bombay Stock Exchange
            "NSE": ".NS",     # National Stock Exchange of India
            "HKG": ".HK",     # Hong Kong Stock Exchange
            "TYO": ".T",      # Tokyo Stock Exchange
            "CSE": ".CSE",    # Casablanca Stock Exchange (Morocco)
            "CASABLANCA": ".CSE",
        }
        
        suffix = exchange_suffixes.get(symbol.exchange, "")
        return f"{symbol.ticker}{suffix}"
    
    async def get_company_info(self, symbol: Symbol) -> Optional[Dict[str, Any]]:
        """Get company information."""
        try:
            yahoo_symbol = self._normalize_symbol(symbol)
            
            # Use Yahoo Finance quoteSummary API
            url = f"{self.base_url}/v10/finance/quoteSummary/{yahoo_symbol}"
            params = {
                "modules": "assetProfile,summaryProfile,summaryDetail,esgScores,price,incomeStatementHistory,incomeStatementHistoryQuarterly,balanceSheetHistory,balanceSheetHistoryQuarterly,cashflowStatementHistory,cashflowStatementHistoryQuarterly,defaultKeyStatistics,financialData,calendarEvents,secFilings,recommendationTrend,upgradeDowngradeHistory,institutionOwnership,fundOwnership,majorDirectHolders,majorHoldersBreakdown,insiderTransactions,insiderHolders,netSharePurchaseActivity,earnings,earningsHistory,earningsTrend,industryTrend,indexTrend,sectorTrend"
            }
            
            response = await self._make_request("GET", url, params=params)
            
            if "quoteSummary" in response and response["quoteSummary"]["result"]:
                return response["quoteSummary"]["result"][0]
            
            return None
        
        except Exception as e:
            logger.error(
                "Failed to get company info from Yahoo Finance",
                symbol=symbol.ticker,
                error=str(e),
            )
            return None
    
    async def get_options_chain(self, symbol: Symbol) -> Optional[Dict[str, Any]]:
        """Get options chain data."""
        try:
            yahoo_symbol = self._normalize_symbol(symbol)
            
            url = f"{self.base_url}/v7/finance/options/{yahoo_symbol}"
            
            response = await self._make_request("GET", url)
            
            if "optionChain" in response and response["optionChain"]["result"]:
                return response["optionChain"]["result"][0]
            
            return None
        
        except Exception as e:
            logger.error(
                "Failed to get options chain from Yahoo Finance",
                symbol=symbol.ticker,
                error=str(e),
            )
            return None
    
    async def search_symbols(self, query: str) -> List[Dict[str, Any]]:
        """Search for symbols."""
        try:
            url = f"{self.base_url}/v1/finance/search"
            params = {
                "q": query,
                "quotesCount": 10,
                "newsCount": 0,
            }
            
            response = await self._make_request("GET", url, params=params)
            
            if "quotes" in response:
                return response["quotes"]
            
            return []
        
        except Exception as e:
            logger.error(
                "Failed to search symbols in Yahoo Finance",
                query=query,
                error=str(e),
            )
            return []
    
    async def get_market_news(self, symbol: Optional[Symbol] = None, count: int = 10) -> List[Dict[str, Any]]:
        """Get market news."""
        try:
            if symbol:
                yahoo_symbol = self._normalize_symbol(symbol)
                url = f"{self.base_url}/v1/finance/search"
                params = {
                    "q": yahoo_symbol,
                    "quotesCount": 0,
                    "newsCount": count,
                }
            else:
                # General market news
                url = f"{self.base_url}/v1/finance/trending/US"
                params = {}
            
            response = await self._make_request("GET", url, params=params)
            
            if symbol and "news" in response:
                return response["news"]
            elif not symbol and "finance" in response and "result" in response["finance"]:
                return response["finance"]["result"][0].get("quotes", [])
            
            return []
        
        except Exception as e:
            logger.error(
                "Failed to get market news from Yahoo Finance",
                symbol=symbol.ticker if symbol else "general",
                error=str(e),
            )
            return []
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        # Yahoo Finance doesn't require authentication for basic data
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }


# Register the provider
ProviderFactory.register_provider("yahoo_finance", YahooFinanceProvider)