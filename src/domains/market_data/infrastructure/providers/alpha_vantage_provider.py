"""Alpha Vantage market data provider implementation."""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

import structlog

from ...domain.entities import Symbol, MarketDataPoint, OHLCV, OrderBook, Trade
from ...domain.value_objects import TimeFrame, DataQuality
from .base_provider import BaseMarketDataProvider, ProviderFactory

logger = structlog.get_logger()


class AlphaVantageProvider(BaseMarketDataProvider):
    """Alpha Vantage market data provider."""
    
    def __init__(self, provider_config: Dict[str, Any], session=None):
        super().__init__(provider_config, session)
        self.base_url = "https://www.alphavantage.co/query"
        
        # Alpha Vantage specific configuration
        self.supported_markets = ["US", "GLOBAL"]
        self.supported_data_types = [
            "quote", "intraday", "daily", "weekly", "monthly",
            "global_quote", "search", "forex", "crypto"
        ]
        
        # Timeframe mapping
        self.timeframe_mapping = {
            TimeFrame.MINUTE_1: "1min",
            TimeFrame.MINUTE_5: "5min",
            TimeFrame.MINUTE_15: "15min",
            TimeFrame.MINUTE_30: "30min",
            TimeFrame.HOUR_1: "60min",
            TimeFrame.DAY_1: "daily",
            TimeFrame.WEEK_1: "weekly",
            TimeFrame.MONTH_1: "monthly",
        }
    
    async def get_real_time_quote(self, symbol: Symbol) -> Optional[MarketDataPoint]:
        """Get real-time quote for symbol."""
        try:
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": self._normalize_symbol(symbol),
                "apikey": self.api_key,
            }
            
            url = f"{self.base_url}?{urlencode(params)}"
            response = await self._make_request("GET", url)
            
            # Parse Alpha Vantage response
            if "Global Quote" in response:
                quote_data = response["Global Quote"]
                
                return MarketDataPoint(
                    symbol=symbol,
                    timestamp=self._parse_timestamp(quote_data.get("07. latest trading day", "")),
                    price=Decimal(quote_data.get("05. price", "0")),
                    volume=Decimal(quote_data.get("06. volume", "0")) if quote_data.get("06. volume") else None,
                    provider=self.name,
                    quality=DataQuality.DELAYED,  # Alpha Vantage free tier is delayed
                    metadata={
                        "open": quote_data.get("02. open"),
                        "high": quote_data.get("03. high"),
                        "low": quote_data.get("04. low"),
                        "previous_close": quote_data.get("08. previous close"),
                        "change": quote_data.get("09. change"),
                        "change_percent": quote_data.get("10. change percent"),
                    }
                )
            
            elif "Error Message" in response:
                logger.error(
                    "Alpha Vantage API error",
                    symbol=symbol.ticker,
                    error=response["Error Message"],
                )
                return None
            
            elif "Note" in response:
                logger.warning(
                    "Alpha Vantage rate limit or notice",
                    symbol=symbol.ticker,
                    note=response["Note"],
                )
                return None
            
            else:
                logger.warning(
                    "Unexpected Alpha Vantage response format",
                    symbol=symbol.ticker,
                    response_keys=list(response.keys()),
                )
                return None
        
        except Exception as e:
            logger.error(
                "Failed to get real-time quote from Alpha Vantage",
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
            # Determine function based on timeframe
            if timeframe in [TimeFrame.MINUTE_1, TimeFrame.MINUTE_5, TimeFrame.MINUTE_15, TimeFrame.MINUTE_30, TimeFrame.HOUR_1]:
                function = "TIME_SERIES_INTRADAY"
                interval = self.timeframe_mapping[timeframe]
                params = {
                    "function": function,
                    "symbol": self._normalize_symbol(symbol),
                    "interval": interval,
                    "apikey": self.api_key,
                    "outputsize": "full",  # Get full data
                }
            elif timeframe == TimeFrame.DAY_1:
                function = "TIME_SERIES_DAILY"
                params = {
                    "function": function,
                    "symbol": self._normalize_symbol(symbol),
                    "apikey": self.api_key,
                    "outputsize": "full",
                }
            elif timeframe == TimeFrame.WEEK_1:
                function = "TIME_SERIES_WEEKLY"
                params = {
                    "function": function,
                    "symbol": self._normalize_symbol(symbol),
                    "apikey": self.api_key,
                }
            elif timeframe == TimeFrame.MONTH_1:
                function = "TIME_SERIES_MONTHLY"
                params = {
                    "function": function,
                    "symbol": self._normalize_symbol(symbol),
                    "apikey": self.api_key,
                }
            else:
                logger.error("Unsupported timeframe for Alpha Vantage", timeframe=timeframe)
                return []
            
            url = f"{self.base_url}?{urlencode(params)}"
            response = await self._make_request("GET", url)
            
            # Parse response based on function
            time_series_key = self._get_time_series_key(function, interval if 'interval' in locals() else None)
            
            if time_series_key not in response:
                if "Error Message" in response:
                    logger.error(
                        "Alpha Vantage API error",
                        symbol=symbol.ticker,
                        error=response["Error Message"],
                    )
                elif "Note" in response:
                    logger.warning(
                        "Alpha Vantage rate limit or notice",
                        symbol=symbol.ticker,
                        note=response["Note"],
                    )
                return []
            
            time_series_data = response[time_series_key]
            ohlcv_list = []
            
            for timestamp_str, data in time_series_data.items():
                timestamp = self._parse_timestamp(timestamp_str)
                
                # Filter by date range
                if timestamp < start_time or timestamp > end_time:
                    continue
                
                ohlcv = OHLCV(
                    symbol=symbol,
                    timestamp=timestamp,
                    open_price=Decimal(data.get("1. open", "0")),
                    high_price=Decimal(data.get("2. high", "0")),
                    low_price=Decimal(data.get("3. low", "0")),
                    close_price=Decimal(data.get("4. close", "0")),
                    volume=Decimal(data.get("5. volume", "0")),
                    timeframe=timeframe.value,
                    provider=self.name,
                )
                
                ohlcv_list.append(ohlcv)
            
            # Sort by timestamp
            ohlcv_list.sort(key=lambda x: x.timestamp)
            
            return ohlcv_list
        
        except Exception as e:
            logger.error(
                "Failed to get historical OHLCV from Alpha Vantage",
                symbol=symbol.ticker,
                timeframe=timeframe,
                error=str(e),
            )
            return []
    
    async def get_order_book(self, symbol: Symbol, depth: int = 10) -> Optional[OrderBook]:
        """Get order book data."""
        # Alpha Vantage doesn't provide order book data
        logger.warning(
            "Order book data not available from Alpha Vantage",
            symbol=symbol.ticker,
        )
        return None
    
    async def get_recent_trades(self, symbol: Symbol, limit: int = 100) -> List[Trade]:
        """Get recent trades."""
        # Alpha Vantage doesn't provide individual trade data
        logger.warning(
            "Individual trade data not available from Alpha Vantage",
            symbol=symbol.ticker,
        )
        return []
    
    def supports_symbol(self, symbol: Symbol) -> bool:
        """Check if provider supports the symbol."""
        # Alpha Vantage supports most US stocks and some international
        if symbol.is_us_market:
            return True
        
        # Check if it's a major international symbol
        major_exchanges = ["LSE", "TSE", "FRA", "AMS", "SWX", "BOM", "NSE"]
        return symbol.exchange in major_exchanges
    
    def supports_data_type(self, data_type: str) -> bool:
        """Check if provider supports the data type."""
        return data_type.lower() in [dt.lower() for dt in self.supported_data_types]
    
    def get_supported_timeframes(self) -> List[TimeFrame]:
        """Get supported timeframes."""
        return list(self.timeframe_mapping.keys())
    
    async def _test_connection(self) -> bool:
        """Test connection to Alpha Vantage API."""
        try:
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": "AAPL",  # Test with Apple stock
                "apikey": self.api_key,
            }
            
            url = f"{self.base_url}?{urlencode(params)}"
            response = await self._make_request("GET", url)
            
            # Check if we got a valid response
            return "Global Quote" in response or "Error Message" in response
        
        except Exception as e:
            logger.error("Alpha Vantage connection test failed", error=str(e))
            return False
    
    def _get_time_series_key(self, function: str, interval: Optional[str] = None) -> str:
        """Get the time series key for the response."""
        if function == "TIME_SERIES_INTRADAY":
            return f"Time Series ({interval})"
        elif function == "TIME_SERIES_DAILY":
            return "Time Series (Daily)"
        elif function == "TIME_SERIES_WEEKLY":
            return "Weekly Time Series"
        elif function == "TIME_SERIES_MONTHLY":
            return "Monthly Time Series"
        else:
            return "Time Series"
    
    def _normalize_symbol(self, symbol: Symbol) -> str:
        """Normalize symbol for Alpha Vantage."""
        # Alpha Vantage uses ticker symbols directly for US stocks
        if symbol.is_us_market:
            return symbol.ticker
        
        # For international stocks, might need exchange suffix
        # This is a simplified implementation
        exchange_suffixes = {
            "LSE": ".LON",
            "TSE": ".TRT",
            "FRA": ".FRK",
            "AMS": ".AMS",
        }
        
        suffix = exchange_suffixes.get(symbol.exchange, "")
        return f"{symbol.ticker}{suffix}"
    
    async def search_symbols(self, keywords: str) -> List[Dict[str, Any]]:
        """Search for symbols using keywords."""
        try:
            params = {
                "function": "SYMBOL_SEARCH",
                "keywords": keywords,
                "apikey": self.api_key,
            }
            
            url = f"{self.base_url}?{urlencode(params)}"
            response = await self._make_request("GET", url)
            
            if "bestMatches" in response:
                return response["bestMatches"]
            
            return []
        
        except Exception as e:
            logger.error(
                "Failed to search symbols in Alpha Vantage",
                keywords=keywords,
                error=str(e),
            )
            return []
    
    async def get_forex_rate(self, from_currency: str, to_currency: str) -> Optional[Dict[str, Any]]:
        """Get forex exchange rate."""
        try:
            params = {
                "function": "CURRENCY_EXCHANGE_RATE",
                "from_currency": from_currency,
                "to_currency": to_currency,
                "apikey": self.api_key,
            }
            
            url = f"{self.base_url}?{urlencode(params)}"
            response = await self._make_request("GET", url)
            
            if "Realtime Currency Exchange Rate" in response:
                return response["Realtime Currency Exchange Rate"]
            
            return None
        
        except Exception as e:
            logger.error(
                "Failed to get forex rate from Alpha Vantage",
                from_currency=from_currency,
                to_currency=to_currency,
                error=str(e),
            )
            return None
    
    async def get_crypto_quote(self, symbol: str, market: str = "USD") -> Optional[Dict[str, Any]]:
        """Get cryptocurrency quote."""
        try:
            params = {
                "function": "CURRENCY_EXCHANGE_RATE",
                "from_currency": symbol,
                "to_currency": market,
                "apikey": self.api_key,
            }
            
            url = f"{self.base_url}?{urlencode(params)}"
            response = await self._make_request("GET", url)
            
            if "Realtime Currency Exchange Rate" in response:
                return response["Realtime Currency Exchange Rate"]
            
            return None
        
        except Exception as e:
            logger.error(
                "Failed to get crypto quote from Alpha Vantage",
                symbol=symbol,
                market=market,
                error=str(e),
            )
            return None
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        # Alpha Vantage uses API key in query parameters, not headers
        return {}


# Register the provider
ProviderFactory.register_provider("alpha_vantage", AlphaVantageProvider)