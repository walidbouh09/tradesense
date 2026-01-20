"""REST API for market data engine."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import structlog

from ..application.services import MarketDataService, CacheService, DataQualityService
from ..domain.entities import Symbol, MarketType
from ..domain.value_objects import TimeFrame, MarketDataRequest
from ....infrastructure.common.rate_limiter import RateLimiter
from ....infrastructure.common.auth import get_current_user

logger = structlog.get_logger()

# Create router
router = APIRouter(prefix="/api/v1/market-data", tags=["market-data"])


# Request/Response Models
class SymbolRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    exchange: str = Field(..., description="Exchange code")
    market: str = Field(default="US", description="Market identifier")
    instrument_type: MarketType = Field(default=MarketType.STOCK, description="Instrument type")
    currency: str = Field(default="USD", description="Currency code")


class QuoteRequest(BaseModel):
    symbols: List[str] = Field(..., description="List of symbols to quote")
    preferred_providers: Optional[List[str]] = Field(None, description="Preferred data providers")
    include_extended_hours: bool = Field(False, description="Include extended hours data")


class HistoricalDataRequest(BaseModel):
    symbols: List[str] = Field(..., description="List of symbols")
    start_date: datetime = Field(..., description="Start date for historical data")
    end_date: datetime = Field(..., description="End date for historical data")
    timeframe: TimeFrame = Field(TimeFrame.DAY_1, description="Data timeframe")
    adjust_for_splits: bool = Field(True, description="Adjust for stock splits")
    adjust_for_dividends: bool = Field(False, description="Adjust for dividends")
    preferred_providers: Optional[List[str]] = Field(None, description="Preferred data providers")


class MarketStatusResponse(BaseModel):
    market: str
    status: str
    next_open: Optional[datetime]
    next_close: Optional[datetime]
    timezone: str
    trading_hours: Dict[str, Any]


class QuoteResponse(BaseModel):
    symbol: str
    price: float
    volume: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    timestamp: datetime
    provider: str
    quality: str
    metadata: Dict[str, Any]


class HistoricalDataResponse(BaseModel):
    symbol: str
    timeframe: str
    data: List[Dict[str, Any]]
    provider: str
    metadata: Dict[str, Any]


class CacheStatsResponse(BaseModel):
    hits: int
    misses: int
    hit_rate_percent: float
    local_cache_size: int
    total_requests: int


class ProviderStatusResponse(BaseModel):
    provider: str
    status: str
    latency_ms: int
    error_rate: float
    last_check: datetime


# Dependency injection
async def get_market_data_service() -> MarketDataService:
    # This would be injected from the application container
    # For now, return a placeholder
    raise HTTPException(status_code=500, detail="Service not configured")


async def get_cache_service() -> CacheService:
    # This would be injected from the application container
    raise HTTPException(status_code=500, detail="Service not configured")


async def get_quality_service() -> DataQualityService:
    # This would be injected from the application container
    raise HTTPException(status_code=500, detail="Service not configured")


async def get_rate_limiter() -> RateLimiter:
    # This would be injected from the application container
    raise HTTPException(status_code=500, detail="Service not configured")


# Rate limiting decorator
async def check_rate_limit(
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    user_id: Optional[UUID] = Depends(get_current_user),
):
    """Check rate limits for API requests."""
    if not rate_limiter.can_make_request():
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
            headers={"Retry-After": "60"}
        )
    
    if not rate_limiter.consume_token():
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
            headers={"Retry-After": "60"}
        )


# Real-time Data Endpoints
@router.get("/quote/{symbol}", response_model=QuoteResponse)
async def get_quote(
    symbol: str,
    exchange: str = Query("NYSE", description="Exchange code"),
    preferred_providers: Optional[str] = Query(None, description="Comma-separated provider names"),
    include_extended_hours: bool = Query(False, description="Include extended hours data"),
    market_data_service: MarketDataService = Depends(get_market_data_service),
    _: None = Depends(check_rate_limit),
):
    """Get real-time quote for a single symbol."""
    try:
        # Parse preferred providers
        providers = preferred_providers.split(",") if preferred_providers else None
        
        # Create symbol object
        symbol_obj = Symbol(
            ticker=symbol.upper(),
            exchange=exchange.upper(),
            market="US" if exchange.upper() in ["NYSE", "NASDAQ", "AMEX"] else "GLOBAL",
            instrument_type=MarketType.STOCK,
        )
        
        # Get quote data
        response = await market_data_service.get_real_time_data(
            symbols=[symbol],
            data_types=["quote"],
            preferred_providers=providers,
        )
        
        if not response.is_successful:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get quote: {', '.join(response.errors)}"
            )
        
        # Extract quote data
        quote_data = response.data.get(symbol, {})
        
        return QuoteResponse(
            symbol=symbol,
            price=quote_data.get("price", 0.0),
            volume=quote_data.get("volume"),
            bid=quote_data.get("bid"),
            ask=quote_data.get("ask"),
            timestamp=response.timestamp,
            provider=response.provider,
            quality=response.quality,
            metadata=response.metadata,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get quote", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/quotes", response_model=List[QuoteResponse])
async def get_quotes(
    request: QuoteRequest,
    market_data_service: MarketDataService = Depends(get_market_data_service),
    _: None = Depends(check_rate_limit),
):
    """Get real-time quotes for multiple symbols."""
    try:
        response = await market_data_service.get_real_time_data(
            symbols=request.symbols,
            data_types=["quote"],
            preferred_providers=request.preferred_providers,
        )
        
        if not response.is_successful:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get quotes: {', '.join(response.errors)}"
            )
        
        # Convert response to list of quotes
        quotes = []
        for symbol in request.symbols:
            quote_data = response.data.get(symbol, {})
            quotes.append(QuoteResponse(
                symbol=symbol,
                price=quote_data.get("price", 0.0),
                volume=quote_data.get("volume"),
                bid=quote_data.get("bid"),
                ask=quote_data.get("ask"),
                timestamp=response.timestamp,
                provider=response.provider,
                quality=response.quality,
                metadata=response.metadata,
            ))
        
        return quotes
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get quotes", symbols=request.symbols, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


# Historical Data Endpoints
@router.get("/historical/{symbol}", response_model=HistoricalDataResponse)
async def get_historical_data(
    symbol: str,
    start_date: datetime = Query(..., description="Start date (ISO format)"),
    end_date: datetime = Query(..., description="End date (ISO format)"),
    timeframe: TimeFrame = Query(TimeFrame.DAY_1, description="Data timeframe"),
    exchange: str = Query("NYSE", description="Exchange code"),
    adjust_for_splits: bool = Query(True, description="Adjust for stock splits"),
    adjust_for_dividends: bool = Query(False, description="Adjust for dividends"),
    preferred_providers: Optional[str] = Query(None, description="Comma-separated provider names"),
    market_data_service: MarketDataService = Depends(get_market_data_service),
    _: None = Depends(check_rate_limit),
):
    """Get historical data for a single symbol."""
    try:
        # Validate date range
        if start_date >= end_date:
            raise HTTPException(
                status_code=400,
                detail="Start date must be before end date"
            )
        
        # Check if date range is reasonable
        if (end_date - start_date).days > 365 * 5:  # 5 years max
            raise HTTPException(
                status_code=400,
                detail="Date range too large. Maximum 5 years allowed."
            )
        
        # Parse preferred providers
        providers = preferred_providers.split(",") if preferred_providers else None
        
        # Get historical data
        response = await market_data_service.get_historical_data(
            symbols=[symbol],
            data_types=["ohlcv"],
            start_time=start_date,
            end_time=end_date,
            timeframe=timeframe.value,
            preferred_providers=providers,
        )
        
        if not response.is_successful:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get historical data: {', '.join(response.errors)}"
            )
        
        # Extract historical data
        historical_data = response.data.get(symbol, [])
        
        return HistoricalDataResponse(
            symbol=symbol,
            timeframe=timeframe.value,
            data=historical_data,
            provider=response.provider,
            metadata=response.metadata,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get historical data", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/historical", response_model=List[HistoricalDataResponse])
async def get_historical_data_bulk(
    request: HistoricalDataRequest,
    market_data_service: MarketDataService = Depends(get_market_data_service),
    _: None = Depends(check_rate_limit),
):
    """Get historical data for multiple symbols."""
    try:
        # Validate request
        if request.start_date >= request.end_date:
            raise HTTPException(
                status_code=400,
                detail="Start date must be before end date"
            )
        
        if len(request.symbols) > 50:  # Limit bulk requests
            raise HTTPException(
                status_code=400,
                detail="Too many symbols. Maximum 50 symbols per request."
            )
        
        response = await market_data_service.get_historical_data(
            symbols=request.symbols,
            data_types=["ohlcv"],
            start_time=request.start_date,
            end_time=request.end_date,
            timeframe=request.timeframe.value,
            preferred_providers=request.preferred_providers,
        )
        
        if not response.is_successful:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get historical data: {', '.join(response.errors)}"
            )
        
        # Convert response to list
        historical_responses = []
        for symbol in request.symbols:
            historical_data = response.data.get(symbol, [])
            historical_responses.append(HistoricalDataResponse(
                symbol=symbol,
                timeframe=request.timeframe.value,
                data=historical_data,
                provider=response.provider,
                metadata=response.metadata,
            ))
        
        return historical_responses
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get bulk historical data", symbols=request.symbols, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


# Market Information Endpoints
@router.get("/markets/{market}/status", response_model=MarketStatusResponse)
async def get_market_status(
    market: str,
    market_data_service: MarketDataService = Depends(get_market_data_service),
):
    """Get market status and trading hours."""
    try:
        # This would query market status from the service
        # For now, return mock data
        
        market_upper = market.upper()
        
        if market_upper == "US":
            return MarketStatusResponse(
                market="US",
                status="open",  # This would be calculated based on current time
                next_open=datetime.utcnow().replace(hour=14, minute=30, second=0, microsecond=0),
                next_close=datetime.utcnow().replace(hour=21, minute=0, second=0, microsecond=0),
                timezone="America/New_York",
                trading_hours={
                    "regular": {"open": "09:30", "close": "16:00"},
                    "extended": {"pre_open": "04:00", "post_close": "20:00"}
                }
            )
        elif market_upper == "MOROCCO":
            return MarketStatusResponse(
                market="MOROCCO",
                status="closed",
                next_open=datetime.utcnow().replace(hour=9, minute=30, second=0, microsecond=0),
                next_close=datetime.utcnow().replace(hour=15, minute=30, second=0, microsecond=0),
                timezone="Africa/Casablanca",
                trading_hours={
                    "regular": {"open": "09:30", "close": "15:30"}
                }
            )
        else:
            raise HTTPException(status_code=404, detail="Market not found")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get market status", market=market, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/markets/{market}/symbols")
async def get_market_symbols(
    market: str,
    limit: int = Query(100, description="Maximum number of symbols to return"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get list of symbols for a market."""
    try:
        # This would query symbols from a symbol master database
        # For now, return mock data
        
        market_upper = market.upper()
        
        if market_upper == "US":
            symbols = [
                {"ticker": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ"},
                {"ticker": "MSFT", "name": "Microsoft Corporation", "exchange": "NASDAQ"},
                {"ticker": "GOOGL", "name": "Alphabet Inc.", "exchange": "NASDAQ"},
                {"ticker": "AMZN", "name": "Amazon.com Inc.", "exchange": "NASDAQ"},
                {"ticker": "TSLA", "name": "Tesla Inc.", "exchange": "NASDAQ"},
            ]
        elif market_upper == "MOROCCO":
            symbols = [
                {"ticker": "ATW", "name": "Attijariwafa Bank", "exchange": "CSE"},
                {"ticker": "BCP", "name": "Banque Centrale Populaire", "exchange": "CSE"},
                {"ticker": "IAM", "name": "Maroc Telecom", "exchange": "CSE"},
                {"ticker": "LHM", "name": "LafargeHolcim Maroc", "exchange": "CSE"},
                {"ticker": "MNG", "name": "Managem", "exchange": "CSE"},
            ]
        else:
            raise HTTPException(status_code=404, detail="Market not found")
        
        # Apply pagination
        paginated_symbols = symbols[offset:offset + limit]
        
        return {
            "market": market_upper,
            "symbols": paginated_symbols,
            "total": len(symbols),
            "limit": limit,
            "offset": offset,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get market symbols", market=market, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


# System Status Endpoints
@router.get("/providers/status", response_model=List[ProviderStatusResponse])
async def get_providers_status(
    market_data_service: MarketDataService = Depends(get_market_data_service),
):
    """Get status of all data providers."""
    try:
        # This would check the health of all providers
        # For now, return mock data
        
        providers_status = [
            ProviderStatusResponse(
                provider="alpha_vantage",
                status="healthy",
                latency_ms=150,
                error_rate=0.02,
                last_check=datetime.utcnow(),
            ),
            ProviderStatusResponse(
                provider="yahoo_finance",
                status="healthy",
                latency_ms=80,
                error_rate=0.01,
                last_check=datetime.utcnow(),
            ),
        ]
        
        return providers_status
    
    except Exception as e:
        logger.error("Failed to get providers status", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    cache_service: CacheService = Depends(get_cache_service),
):
    """Get cache statistics."""
    try:
        stats = cache_service.get_stats()
        
        return CacheStatsResponse(
            hits=stats["hits"],
            misses=stats["misses"],
            hit_rate_percent=stats["hit_rate_percent"],
            local_cache_size=stats["local_cache_size"],
            total_requests=stats["total_requests"],
        )
    
    except Exception as e:
        logger.error("Failed to get cache stats", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/cache/invalidate")
async def invalidate_cache(
    pattern: str = Query(..., description="Cache key pattern to invalidate"),
    cache_service: CacheService = Depends(get_cache_service),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Invalidate cache entries matching pattern."""
    try:
        # Run cache invalidation in background
        background_tasks.add_task(cache_service.invalidate, pattern)
        
        return {"message": f"Cache invalidation started for pattern: {pattern}"}
    
    except Exception as e:
        logger.error("Failed to invalidate cache", pattern=pattern, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/quality/report")
async def get_quality_report(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    data_type: Optional[str] = Query(None, description="Filter by data type"),
    hours: int = Query(24, description="Report period in hours"),
    quality_service: DataQualityService = Depends(get_quality_service),
):
    """Get data quality report."""
    try:
        report = quality_service.get_quality_report(
            provider=provider,
            symbol=symbol,
            data_type=data_type,
            hours=hours,
        )
        
        return report
    
    except Exception as e:
        logger.error("Failed to get quality report", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


# Search Endpoints
@router.get("/search")
async def search_symbols(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Maximum results"),
    market_data_service: MarketDataService = Depends(get_market_data_service),
):
    """Search for symbols by name or ticker."""
    try:
        # This would search across multiple providers
        # For now, return mock data
        
        results = [
            {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "exchange": "NASDAQ",
                "market": "US",
                "type": "stock",
                "currency": "USD",
            },
            {
                "ticker": "MSFT",
                "name": "Microsoft Corporation",
                "exchange": "NASDAQ",
                "market": "US",
                "type": "stock",
                "currency": "USD",
            },
        ]
        
        # Filter results based on query
        filtered_results = [
            result for result in results
            if query.lower() in result["ticker"].lower() or query.lower() in result["name"].lower()
        ]
        
        return {
            "query": query,
            "results": filtered_results[:limit],
            "total": len(filtered_results),
        }
    
    except Exception as e:
        logger.error("Failed to search symbols", query=query, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")