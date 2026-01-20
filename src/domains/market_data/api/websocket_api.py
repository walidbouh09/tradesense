"""WebSocket API for real-time market data streaming."""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Set, Any
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.routing import APIRouter
import structlog

from ..application.services import MarketDataService
from ..domain.value_objects import MarketDataSubscription
from ....infrastructure.common.auth import get_current_user_ws
from ....infrastructure.common.rate_limiter import RateLimiter

logger = structlog.get_logger()

# Create router
router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections and subscriptions."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> connection_ids
        self.connection_subscriptions: Dict[str, Set[str]] = {}  # connection_id -> subscription_ids
        self.subscription_connections: Dict[str, Set[str]] = {}  # subscription_id -> connection_ids
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: Optional[str] = None) -> str:
        """Accept WebSocket connection and return connection ID."""
        await websocket.accept()
        
        connection_id = str(uuid4())
        self.active_connections[connection_id] = websocket
        self.connection_subscriptions[connection_id] = set()
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
        
        self.connection_metadata[connection_id] = {
            "user_id": user_id,
            "connected_at": datetime.utcnow(),
            "message_count": 0,
            "last_activity": datetime.utcnow(),
        }
        
        logger.info(
            "WebSocket connection established",
            connection_id=connection_id,
            user_id=user_id,
            total_connections=len(self.active_connections),
        )
        
        return connection_id
    
    def disconnect(self, connection_id: str):
        """Remove WebSocket connection."""
        if connection_id not in self.active_connections:
            return
        
        # Remove from active connections
        del self.active_connections[connection_id]
        
        # Remove from user connections
        metadata = self.connection_metadata.get(connection_id, {})
        user_id = metadata.get("user_id")
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # Remove subscriptions
        if connection_id in self.connection_subscriptions:
            subscription_ids = self.connection_subscriptions[connection_id].copy()
            for subscription_id in subscription_ids:
                self.unsubscribe(connection_id, subscription_id)
            del self.connection_subscriptions[connection_id]
        
        # Remove metadata
        if connection_id in self.connection_metadata:
            del self.connection_metadata[connection_id]
        
        logger.info(
            "WebSocket connection closed",
            connection_id=connection_id,
            user_id=user_id,
            total_connections=len(self.active_connections),
        )
    
    def subscribe(self, connection_id: str, subscription_id: str):
        """Add subscription to connection."""
        if connection_id not in self.connection_subscriptions:
            self.connection_subscriptions[connection_id] = set()
        
        self.connection_subscriptions[connection_id].add(subscription_id)
        
        if subscription_id not in self.subscription_connections:
            self.subscription_connections[subscription_id] = set()
        
        self.subscription_connections[subscription_id].add(connection_id)
        
        logger.debug(
            "Subscription added",
            connection_id=connection_id,
            subscription_id=subscription_id,
        )
    
    def unsubscribe(self, connection_id: str, subscription_id: str):
        """Remove subscription from connection."""
        if connection_id in self.connection_subscriptions:
            self.connection_subscriptions[connection_id].discard(subscription_id)
        
        if subscription_id in self.subscription_connections:
            self.subscription_connections[subscription_id].discard(connection_id)
            
            # Remove subscription if no connections
            if not self.subscription_connections[subscription_id]:
                del self.subscription_connections[subscription_id]
        
        logger.debug(
            "Subscription removed",
            connection_id=connection_id,
            subscription_id=subscription_id,
        )
    
    async def send_personal_message(self, message: Dict[str, Any], connection_id: str):
        """Send message to specific connection."""
        if connection_id not in self.active_connections:
            return False
        
        try:
            websocket = self.active_connections[connection_id]
            await websocket.send_text(json.dumps(message))
            
            # Update metadata
            if connection_id in self.connection_metadata:
                self.connection_metadata[connection_id]["message_count"] += 1
                self.connection_metadata[connection_id]["last_activity"] = datetime.utcnow()
            
            return True
        
        except Exception as e:
            logger.error(
                "Failed to send personal message",
                connection_id=connection_id,
                error=str(e),
            )
            # Remove broken connection
            self.disconnect(connection_id)
            return False
    
    async def broadcast_to_subscription(self, message: Dict[str, Any], subscription_id: str):
        """Broadcast message to all connections with specific subscription."""
        if subscription_id not in self.subscription_connections:
            return 0
        
        connection_ids = self.subscription_connections[subscription_id].copy()
        successful_sends = 0
        
        for connection_id in connection_ids:
            if await self.send_personal_message(message, connection_id):
                successful_sends += 1
        
        return successful_sends
    
    async def broadcast_to_user(self, message: Dict[str, Any], user_id: str):
        """Broadcast message to all connections for a user."""
        if user_id not in self.user_connections:
            return 0
        
        connection_ids = self.user_connections[user_id].copy()
        successful_sends = 0
        
        for connection_id in connection_ids:
            if await self.send_personal_message(message, connection_id):
                successful_sends += 1
        
        return successful_sends
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        total_connections = len(self.active_connections)
        total_subscriptions = len(self.subscription_connections)
        unique_users = len(self.user_connections)
        
        # Calculate average messages per connection
        total_messages = sum(
            metadata.get("message_count", 0)
            for metadata in self.connection_metadata.values()
        )
        avg_messages = total_messages / max(1, total_connections)
        
        return {
            "total_connections": total_connections,
            "total_subscriptions": total_subscriptions,
            "unique_users": unique_users,
            "total_messages_sent": total_messages,
            "average_messages_per_connection": avg_messages,
        }


# Global connection manager
manager = ConnectionManager()


class WebSocketMessageHandler:
    """Handles incoming WebSocket messages."""
    
    def __init__(self, market_data_service: MarketDataService, rate_limiter: RateLimiter):
        self.market_data_service = market_data_service
        self.rate_limiter = rate_limiter
    
    async def handle_message(self, websocket: WebSocket, connection_id: str, message: Dict[str, Any]):
        """Handle incoming WebSocket message."""
        try:
            action = message.get("action")
            
            if not action:
                await self._send_error(websocket, "Missing 'action' field")
                return
            
            # Check rate limits
            if not self.rate_limiter.can_make_request():
                await self._send_error(websocket, "Rate limit exceeded")
                return
            
            if action == "subscribe":
                await self._handle_subscribe(websocket, connection_id, message)
            elif action == "unsubscribe":
                await self._handle_unsubscribe(websocket, connection_id, message)
            elif action == "ping":
                await self._handle_ping(websocket, connection_id, message)
            elif action == "get_subscriptions":
                await self._handle_get_subscriptions(websocket, connection_id)
            else:
                await self._send_error(websocket, f"Unknown action: {action}")
        
        except Exception as e:
            logger.error(
                "Error handling WebSocket message",
                connection_id=connection_id,
                error=str(e),
                message=message,
            )
            await self._send_error(websocket, "Internal server error")
    
    async def _handle_subscribe(self, websocket: WebSocket, connection_id: str, message: Dict[str, Any]):
        """Handle subscription request."""
        try:
            symbols = message.get("symbols", [])
            data_types = message.get("data_types", ["quote"])
            markets = message.get("markets", [])
            filters = message.get("filters", {})
            
            if not symbols:
                await self._send_error(websocket, "Missing 'symbols' field")
                return
            
            # Create subscription
            subscription_id = str(uuid4())
            subscription = MarketDataSubscription(
                subscription_id=subscription_id,
                symbols=symbols,
                data_types=data_types,
                markets=markets,
                filters=filters,
            )
            
            # Subscribe to market data service
            success = await self.market_data_service.subscribe_real_time(subscription)
            
            if success:
                # Add to connection manager
                manager.subscribe(connection_id, subscription_id)
                
                await self._send_response(websocket, {
                    "action": "subscribe",
                    "status": "success",
                    "subscription_id": subscription_id,
                    "symbols": symbols,
                    "data_types": data_types,
                })
                
                logger.info(
                    "WebSocket subscription created",
                    connection_id=connection_id,
                    subscription_id=subscription_id,
                    symbols=symbols,
                )
            else:
                await self._send_error(websocket, "Failed to create subscription")
        
        except Exception as e:
            logger.error("Failed to handle subscribe", error=str(e))
            await self._send_error(websocket, "Failed to create subscription")
    
    async def _handle_unsubscribe(self, websocket: WebSocket, connection_id: str, message: Dict[str, Any]):
        """Handle unsubscription request."""
        try:
            subscription_id = message.get("subscription_id")
            
            if not subscription_id:
                await self._send_error(websocket, "Missing 'subscription_id' field")
                return
            
            # Unsubscribe from market data service
            success = await self.market_data_service.unsubscribe_real_time(subscription_id)
            
            if success:
                # Remove from connection manager
                manager.unsubscribe(connection_id, subscription_id)
                
                await self._send_response(websocket, {
                    "action": "unsubscribe",
                    "status": "success",
                    "subscription_id": subscription_id,
                })
                
                logger.info(
                    "WebSocket subscription removed",
                    connection_id=connection_id,
                    subscription_id=subscription_id,
                )
            else:
                await self._send_error(websocket, "Failed to remove subscription")
        
        except Exception as e:
            logger.error("Failed to handle unsubscribe", error=str(e))
            await self._send_error(websocket, "Failed to remove subscription")
    
    async def _handle_ping(self, websocket: WebSocket, connection_id: str, message: Dict[str, Any]):
        """Handle ping request."""
        await self._send_response(websocket, {
            "action": "pong",
            "timestamp": datetime.utcnow().isoformat(),
            "connection_id": connection_id,
        })
    
    async def _handle_get_subscriptions(self, websocket: WebSocket, connection_id: str):
        """Handle get subscriptions request."""
        subscriptions = list(manager.connection_subscriptions.get(connection_id, set()))
        
        await self._send_response(websocket, {
            "action": "get_subscriptions",
            "subscriptions": subscriptions,
            "count": len(subscriptions),
        })
    
    async def _send_response(self, websocket: WebSocket, response: Dict[str, Any]):
        """Send response message."""
        response["timestamp"] = datetime.utcnow().isoformat()
        await websocket.send_text(json.dumps(response))
    
    async def _send_error(self, websocket: WebSocket, error_message: str):
        """Send error message."""
        error_response = {
            "action": "error",
            "error": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await websocket.send_text(json.dumps(error_response))


# Dependency injection
async def get_market_data_service() -> MarketDataService:
    # This would be injected from the application container
    raise HTTPException(status_code=500, detail="Service not configured")


async def get_rate_limiter() -> RateLimiter:
    # This would be injected from the application container
    raise HTTPException(status_code=500, detail="Service not configured")


@router.websocket("/ws/market-data")
async def websocket_endpoint(
    websocket: WebSocket,
    market_data_service: MarketDataService = Depends(get_market_data_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    user_id: Optional[str] = Depends(get_current_user_ws),
):
    """WebSocket endpoint for real-time market data."""
    connection_id = await manager.connect(websocket, user_id)
    message_handler = WebSocketMessageHandler(market_data_service, rate_limiter)
    
    try:
        # Send welcome message
        await manager.send_personal_message({
            "action": "connected",
            "connection_id": connection_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Connected to TradeSense Market Data WebSocket",
        }, connection_id)
        
        # Message handling loop
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle message
                await message_handler.handle_message(websocket, connection_id, message)
            
            except json.JSONDecodeError:
                await manager.send_personal_message({
                    "action": "error",
                    "error": "Invalid JSON format",
                    "timestamp": datetime.utcnow().isoformat(),
                }, connection_id)
            
            except WebSocketDisconnect:
                break
    
    except WebSocketDisconnect:
        pass
    
    except Exception as e:
        logger.error(
            "WebSocket error",
            connection_id=connection_id,
            user_id=user_id,
            error=str(e),
        )
    
    finally:
        manager.disconnect(connection_id)


@router.websocket("/ws/market-data/{symbol}")
async def websocket_symbol_endpoint(
    websocket: WebSocket,
    symbol: str,
    data_types: str = "quote",  # Comma-separated data types
    market_data_service: MarketDataService = Depends(get_market_data_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    user_id: Optional[str] = Depends(get_current_user_ws),
):
    """WebSocket endpoint for specific symbol real-time data."""
    connection_id = await manager.connect(websocket, user_id)
    
    try:
        # Parse data types
        data_type_list = [dt.strip() for dt in data_types.split(",")]
        
        # Create automatic subscription
        subscription_id = str(uuid4())
        subscription = MarketDataSubscription(
            subscription_id=subscription_id,
            symbols=[symbol.upper()],
            data_types=data_type_list,
        )
        
        # Subscribe to market data service
        success = await market_data_service.subscribe_real_time(subscription)
        
        if success:
            manager.subscribe(connection_id, subscription_id)
            
            # Send confirmation
            await manager.send_personal_message({
                "action": "auto_subscribed",
                "subscription_id": subscription_id,
                "symbol": symbol.upper(),
                "data_types": data_type_list,
                "timestamp": datetime.utcnow().isoformat(),
            }, connection_id)
            
            # Keep connection alive and handle any incoming messages
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    # Handle ping/pong or other control messages
                    if message.get("action") == "ping":
                        await manager.send_personal_message({
                            "action": "pong",
                            "timestamp": datetime.utcnow().isoformat(),
                        }, connection_id)
                
                except json.JSONDecodeError:
                    await manager.send_personal_message({
                        "action": "error",
                        "error": "Invalid JSON format",
                        "timestamp": datetime.utcnow().isoformat(),
                    }, connection_id)
                
                except WebSocketDisconnect:
                    break
        
        else:
            await manager.send_personal_message({
                "action": "error",
                "error": "Failed to create subscription",
                "timestamp": datetime.utcnow().isoformat(),
            }, connection_id)
    
    except WebSocketDisconnect:
        pass
    
    except Exception as e:
        logger.error(
            "Symbol WebSocket error",
            connection_id=connection_id,
            symbol=symbol,
            error=str(e),
        )
    
    finally:
        manager.disconnect(connection_id)


# Market Data Broadcasting Functions
async def broadcast_market_data(symbol: str, data: Dict[str, Any]):
    """Broadcast market data to all relevant subscriptions."""
    # Find subscriptions that match this symbol
    relevant_subscriptions = []
    
    for subscription_id, connection_ids in manager.subscription_connections.items():
        # This would check if subscription matches the symbol
        # For now, assume all subscriptions are relevant
        relevant_subscriptions.append(subscription_id)
    
    # Broadcast to relevant subscriptions
    message = {
        "action": "market_data",
        "symbol": symbol,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    total_sent = 0
    for subscription_id in relevant_subscriptions:
        sent_count = await manager.broadcast_to_subscription(message, subscription_id)
        total_sent += sent_count
    
    logger.debug(
        "Market data broadcasted",
        symbol=symbol,
        subscriptions=len(relevant_subscriptions),
        connections=total_sent,
    )


async def broadcast_market_status(market: str, status: str):
    """Broadcast market status update."""
    message = {
        "action": "market_status",
        "market": market,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    # Broadcast to all connections
    total_sent = 0
    for connection_id in manager.active_connections.keys():
        if await manager.send_personal_message(message, connection_id):
            total_sent += 1
    
    logger.info(
        "Market status broadcasted",
        market=market,
        status=status,
        connections=total_sent,
    )


async def broadcast_system_message(message_text: str, message_type: str = "info"):
    """Broadcast system message to all connections."""
    message = {
        "action": "system_message",
        "type": message_type,
        "message": message_text,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    # Broadcast to all connections
    total_sent = 0
    for connection_id in manager.active_connections.keys():
        if await manager.send_personal_message(message, connection_id):
            total_sent += 1
    
    logger.info(
        "System message broadcasted",
        message=message_text,
        type=message_type,
        connections=total_sent,
    )


# WebSocket Statistics Endpoint
@router.get("/ws/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics."""
    return manager.get_connection_stats()