"""Base provider abstraction for market data providers."""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID

import aiohttp
import structlog

from ...domain.entities import DataProvider, Symbol, MarketDataPoint, OHLCV, OrderBook, Trade
from ...domain.value_objects import MarketDataRequest, TimeFrame, DataQuality
from .....infrastructure.common.exceptions import ProviderError, RateLimitError

logger = structlog.get_logger()


class BaseMarketDataProvider(ABC):
    """Abstract base class for market data providers."""
    
    def __init__(
        self,
        provider_config: Dict[str, Any],
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self.config = provider_config
        self.session = session
        self.name = provider_config.get("name", "unknown")
        self.base_url = provider_config.get("base_url", "")
        self.api_key = provider_config.get("api_key", "")
        self.rate_limits = provider_config.get("rate_limits", {})
        self.timeout = provider_config.get("timeout_seconds", 30)
        self.retry_attempts = provider_config.get("retry_attempts", 3)
        self.retry_delay = provider_config.get("retry_delay_seconds", 1)
        
        # Request tracking
        self.request_count = 0
        self.error_count = 0
        self.last_request_time: Optional[datetime] = None
        self.last_error_time: Optional[datetime] = None
    
    @abstractmethod
    async def get_real_time_quote(self, symbol: Symbol) -> Optional[MarketDataPoint]:
        """Get real-time quote for symbol."""
        pass
    
    @abstractmethod
    async def get_historical_ohlcv(
        self,
        symbol: Symbol,
        start_time: datetime,
        end_time: datetime,
        timeframe: TimeFrame,
    ) -> List[OHLCV]:
        """Get historical OHLCV data."""
        pass
    
    @abstractmethod
    async def get_order_book(self, symbol: Symbol, depth: int = 10) -> Optional[OrderBook]:
        """Get order book data."""
        pass
    
    @abstractmethod
    async def get_recent_trades(self, symbol: Symbol, limit: int = 100) -> List[Trade]:
        """Get recent trades."""
        pass
    
    @abstractmethod
    def supports_symbol(self, symbol: Symbol) -> bool:
        """Check if provider supports the symbol."""
        pass
    
    @abstractmethod
    def supports_data_type(self, data_type: str) -> bool:
        """Check if provider supports the data type."""
        pass
    
    @abstractmethod
    def get_supported_timeframes(self) -> List[TimeFrame]:
        """Get supported timeframes."""
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on provider."""
        try:
            start_time = datetime.utcnow()
            
            # Try a simple API call
            test_result = await self._test_connection()
            
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return {
                "provider": self.name,
                "status": "healthy" if test_result else "unhealthy",
                "latency_ms": latency_ms,
                "last_check": datetime.utcnow().isoformat(),
                "request_count": self.request_count,
                "error_count": self.error_count,
                "error_rate": self.error_count / max(1, self.request_count),
            }
            
        except Exception as e:
            logger.error("Provider health check failed", provider=self.name, error=str(e))
            return {
                "provider": self.name,
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat(),
            }
    
    @abstractmethod
    async def _test_connection(self) -> bool:
        """Test connection to provider API."""
        pass
    
    async def _make_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic and error handling."""
        if not self.session:
            raise ProviderError(f"No HTTP session available for {self.name}")
        
        # Add API key to headers if required
        request_headers = headers or {}
        if self.api_key and "Authorization" not in request_headers:
            request_headers.update(self._get_auth_headers())
        
        last_exception = None
        
        for attempt in range(self.retry_attempts):
            try:
                self.request_count += 1
                self.last_request_time = datetime.utcnow()
                
                async with self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=request_headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    
                    # Check for rate limiting
                    if response.status == 429:
                        self.error_count += 1
                        self.last_error_time = datetime.utcnow()
                        raise RateLimitError(f"Rate limit exceeded for {self.name}")
                    
                    # Check for other HTTP errors
                    if response.status >= 400:
                        error_text = await response.text()
                        self.error_count += 1
                        self.last_error_time = datetime.utcnow()
                        raise ProviderError(
                            f"HTTP {response.status} from {self.name}: {error_text}"
                        )
                    
                    # Parse JSON response
                    try:
                        return await response.json()
                    except Exception as e:
                        # If JSON parsing fails, return text
                        text_response = await response.text()
                        return {"raw_response": text_response}
            
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e
                self.error_count += 1
                self.last_error_time = datetime.utcnow()
                
                logger.warning(
                    "Request failed, retrying",
                    provider=self.name,
                    attempt=attempt + 1,
                    max_attempts=self.retry_attempts,
                    error=str(e),
                )
                
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
        
        # All attempts failed
        raise ProviderError(
            f"All {self.retry_attempts} attempts failed for {self.name}: {last_exception}"
        )
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        # Default implementation - override in subclasses
        return {"X-API-Key": self.api_key}
    
    def _normalize_symbol(self, symbol: Symbol) -> str:
        """Normalize symbol for this provider."""
        # Default implementation - override in subclasses
        return symbol.ticker
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string to datetime."""
        # Common timestamp formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO format with microseconds
            "%Y-%m-%dT%H:%M:%SZ",     # ISO format
            "%Y-%m-%d %H:%M:%S",      # Standard format
            "%Y-%m-%d",               # Date only
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
        
        # If all formats fail, try parsing as timestamp
        try:
            return datetime.fromtimestamp(float(timestamp_str))
        except (ValueError, TypeError):
            logger.warning(
                "Failed to parse timestamp",
                timestamp=timestamp_str,
                provider=self.name,
            )
            return datetime.utcnow()
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information."""
        return {
            "name": self.name,
            "base_url": self.base_url,
            "supported_markets": self.config.get("supported_markets", []),
            "supported_data_types": self.config.get("supported_data_types", []),
            "rate_limits": self.rate_limits,
            "timeout_seconds": self.timeout,
            "retry_attempts": self.retry_attempts,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "last_request_time": self.last_request_time.isoformat() if self.last_request_time else None,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
        }


class WebSocketProvider(ABC):
    """Abstract base class for WebSocket market data providers."""
    
    def __init__(self, provider_config: Dict[str, Any]):
        self.config = provider_config
        self.name = provider_config.get("name", "unknown")
        self.websocket_url = provider_config.get("websocket_url", "")
        self.api_key = provider_config.get("api_key", "")
        self.reconnect_attempts = provider_config.get("reconnect_attempts", 5)
        self.reconnect_delay = provider_config.get("reconnect_delay_seconds", 5)
        
        self.websocket = None
        self.is_connected = False
        self.subscriptions: Dict[str, Dict] = {}
        self.message_handlers: Dict[str, callable] = {}
        self.connection_task: Optional[asyncio.Task] = None
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to WebSocket."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        pass
    
    @abstractmethod
    async def subscribe(self, symbols: List[str], data_types: List[str]) -> bool:
        """Subscribe to real-time data."""
        pass
    
    @abstractmethod
    async def unsubscribe(self, symbols: List[str], data_types: List[str]) -> bool:
        """Unsubscribe from real-time data."""
        pass
    
    @abstractmethod
    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming WebSocket message."""
        pass
    
    def add_message_handler(self, message_type: str, handler: callable) -> None:
        """Add message handler for specific message type."""
        self.message_handlers[message_type] = handler
    
    def remove_message_handler(self, message_type: str) -> None:
        """Remove message handler."""
        if message_type in self.message_handlers:
            del self.message_handlers[message_type]
    
    async def _reconnect_loop(self) -> None:
        """Reconnection loop for WebSocket."""
        attempt = 0
        
        while attempt < self.reconnect_attempts:
            try:
                logger.info(
                    "Attempting WebSocket reconnection",
                    provider=self.name,
                    attempt=attempt + 1,
                )
                
                if await self.connect():
                    logger.info("WebSocket reconnected successfully", provider=self.name)
                    
                    # Resubscribe to previous subscriptions
                    for subscription_id, subscription in self.subscriptions.items():
                        await self.subscribe(
                            subscription["symbols"],
                            subscription["data_types"],
                        )
                    
                    return
                
            except Exception as e:
                logger.error(
                    "WebSocket reconnection failed",
                    provider=self.name,
                    attempt=attempt + 1,
                    error=str(e),
                )
            
            attempt += 1
            if attempt < self.reconnect_attempts:
                await asyncio.sleep(self.reconnect_delay * attempt)
        
        logger.error(
            "WebSocket reconnection failed after all attempts",
            provider=self.name,
            attempts=self.reconnect_attempts,
        )


class ProviderFactory:
    """Factory for creating market data providers."""
    
    _providers: Dict[str, type] = {}
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type) -> None:
        """Register a provider class."""
        cls._providers[name.lower()] = provider_class
    
    @classmethod
    def create_provider(
        cls,
        provider_name: str,
        config: Dict[str, Any],
        session: Optional[aiohttp.ClientSession] = None,
    ) -> BaseMarketDataProvider:
        """Create provider instance."""
        provider_class = cls._providers.get(provider_name.lower())
        
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        return provider_class(config, session)
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Get list of available provider names."""
        return list(cls._providers.keys())


class ProviderManager:
    """Manager for multiple market data providers."""
    
    def __init__(self):
        self.providers: Dict[str, BaseMarketDataProvider] = {}
        self.websocket_providers: Dict[str, WebSocketProvider] = {}
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self) -> None:
        """Initialize provider manager."""
        self.session = aiohttp.ClientSession()
    
    async def shutdown(self) -> None:
        """Shutdown provider manager."""
        # Disconnect WebSocket providers
        for ws_provider in self.websocket_providers.values():
            await ws_provider.disconnect()
        
        # Close HTTP session
        if self.session:
            await self.session.close()
    
    def add_provider(self, provider: BaseMarketDataProvider) -> None:
        """Add REST API provider."""
        self.providers[provider.name] = provider
    
    def add_websocket_provider(self, provider: WebSocketProvider) -> None:
        """Add WebSocket provider."""
        self.websocket_providers[provider.name] = provider
    
    def get_provider(self, name: str) -> Optional[BaseMarketDataProvider]:
        """Get provider by name."""
        return self.providers.get(name)
    
    def get_websocket_provider(self, name: str) -> Optional[WebSocketProvider]:
        """Get WebSocket provider by name."""
        return self.websocket_providers.get(name)
    
    def get_providers_for_symbol(self, symbol: Symbol) -> List[BaseMarketDataProvider]:
        """Get providers that support the symbol."""
        return [
            provider for provider in self.providers.values()
            if provider.supports_symbol(symbol)
        ]
    
    def get_providers_for_data_type(self, data_type: str) -> List[BaseMarketDataProvider]:
        """Get providers that support the data type."""
        return [
            provider for provider in self.providers.values()
            if provider.supports_data_type(data_type)
        ]
    
    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Perform health check on all providers."""
        results = {}
        
        # Check REST providers
        for name, provider in self.providers.items():
            results[name] = await provider.health_check()
        
        # Check WebSocket providers
        for name, provider in self.websocket_providers.items():
            results[f"{name}_ws"] = {
                "provider": name,
                "type": "websocket",
                "status": "healthy" if provider.is_connected else "unhealthy",
                "connected": provider.is_connected,
                "subscriptions": len(provider.subscriptions),
            }
        
        return results