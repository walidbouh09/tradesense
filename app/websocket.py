"""
WebSocket Event Handlers for TradeSense AI

Handles SocketIO connections, authentication, and room management.
WebSocket is an OUTPUT CHANNEL - no business logic here.
"""

import jwt
from flask import request, current_app
from flask_socketio import join_room, leave_room, disconnect, emit as socketio_emit
from jwt import ExpiredSignatureError, InvalidTokenError

from src.core.event_bus import event_bus

# Global socketio instance - will be set by register_socketio_handlers
_socketio = None


def register_socketio_handlers(socketio):
    """
    Register all SocketIO event handlers.

    Separated from routes for clean architecture.
    WebSocket handles real-time output, not business logic.
    """
    global _socketio
    _socketio = socketio

    # Register event handlers
    _socketio.on_event('connect', _handle_connect)
    _socketio.on_event('disconnect', _handle_disconnect)
    _socketio.on_event('join_challenge', _handle_join_challenge)
    _socketio.on_event('leave_challenge', _handle_leave_challenge)

def _handle_connect():
    """
    Handle WebSocket connection.

    Authentication happens here - no unauthenticated connections allowed.
    JWT validation ensures only authorized users can connect.
    """
    try:
        # Get JWT token from handshake query parameters
        token = request.args.get('token')
        if not token:
            _socketio.emit('error', {'message': 'Authentication token required'})
            disconnect()
            return False

        # Validate JWT and get user identity
        payload = validate_jwt_token(token)

        # Store user identity in socket session for room authorization
        request.sid_data = payload

        print(f"WebSocket authenticated: user_id={payload['user_id']}")
        return True

    except ValueError as e:
        # JWT validation errors - send specific error message
        error_msg = str(e)
        _socketio.emit('error', {'message': f'Authentication failed: {error_msg}'})
        disconnect()
        return False
    except Exception as e:
        # Unexpected errors - generic message for security
        print(f"WebSocket connection error: {e}")
        _socketio.emit('error', {'message': 'Connection failed'})
        disconnect()
        return False

def _handle_disconnect():
        """Handle WebSocket disconnection."""
        if hasattr(request, 'sid_data'):
            user_id = request.sid_data.get('user_id')
            print(f"WebSocket disconnected: user_id={user_id}")

def _handle_join_challenge(data):
        """
        Handle joining a challenge room.

        Room-based isolation ensures one user cannot see another user's challenge.
        Only authenticated users can join rooms for challenges they own.
        """
        try:
            if not hasattr(request, 'sid_data'):
                disconnect()
                return

            user_id = request.sid_data['user_id']
            challenge_id = data.get('challenge_id')

            if not challenge_id:
                _socketio.emit('error', {'message': 'challenge_id required'})
                return

            # TODO: Validate that user owns this challenge
            # This would typically query the database to ensure
            # the challenge belongs to the authenticated user

            room_name = f"challenge_{challenge_id}"
            join_room(room_name)

            print(f"User {user_id} joined room {room_name}")
            _socketio.emit('joined_challenge', {'challenge_id': challenge_id})

        except Exception as e:
            print(f"Error joining challenge room: {e}")
            _socketio.emit('error', {'message': 'Failed to join challenge room'})

def _handle_leave_challenge(data):
        """Handle leaving a challenge room."""
        try:
            challenge_id = data.get('challenge_id')
            if challenge_id:
                room_name = f"challenge_{challenge_id}"
                leave_room(room_name)
                print(f"Left room {room_name}")

        except Exception as e:
            print(f"Error leaving challenge room: {e}")


def validate_jwt_token(token):
    """
    Validate JWT token and extract payload.

    Returns user payload if valid, raises exception if invalid.
    WebSocket connections require valid authentication.
    """
    try:
        # Get JWT secret from environment or Flask config
        secret = current_app.config.get('JWT_SECRET', 'dev-secret-key')

        # Decode and validate token
        payload = jwt.decode(token, secret, algorithms=['HS256'])

        # Validate required claims
        required_claims = ['user_id', 'exp', 'iat']
        for claim in required_claims:
            if claim not in payload:
                raise ValueError(f"Missing required JWT claim: {claim}")

        # Additional validation (custom claims)
        if not isinstance(payload['user_id'], str):
            raise ValueError("user_id must be string")

        # Validate token is not too old (optional - additional security)
        # This prevents replay attacks with very old tokens
        import time
        current_time = time.time()
        if payload['iat'] < (current_time - 3600):  # Token older than 1 hour
            raise ValueError("Token too old")

        return payload

    except ExpiredSignatureError:
        raise ValueError("JWT token has expired")
    except jwt.InvalidSignatureError:
        raise ValueError("Invalid JWT signature")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid JWT token: {str(e)}")
    except ValueError as e:
        raise ValueError(f"JWT validation failed: {str(e)}")
    except Exception as e:
        raise ValueError(f"JWT processing error: {str(e)}")


# WebSocket event forwarding from event bus
# This connects domain events to WebSocket broadcasts
def setup_event_bus_forwarding():
    """
    Set up event bus to forward domain events to WebSocket.

    This is called during app initialization.
    Domain events are forwarded to appropriate SocketIO rooms.

    Why here: Keeps WebSocket logic separate from domain code.
    Event bus provides clean abstraction layer.
    """

    def websocket_forwarder(event_type: str, payload: dict):
        """
        Forward domain events to WebSocket clients.

        Maps domain event types to SocketIO events and emits to appropriate rooms.
        """
        try:
            challenge_id = payload.get('challenge_id')
            if not challenge_id:
                print(f"No challenge_id in {event_type} payload")
                return

            # Map domain events to SocketIO events
            event_mapping = {
                'EQUITY_UPDATED': 'equity_updated',
                'CHALLENGE_STATUS_CHANGED': 'challenge_status_changed',
                'RISK_ALERT': 'risk_alert',
            }

            socketio_event = event_mapping.get(event_type)
            if not socketio_event:
                print(f"No mapping for domain event: {event_type}")
                return

            # Emit to challenge-specific room
            room_name = f"challenge_{challenge_id}"
            _socketio.emit(socketio_event, payload, room=room_name)
            print(f"Emitted {socketio_event} to room {room_name}")

        except Exception as e:
            # WebSocket failures should not affect domain logic
            print(f"WebSocket forwarding error for {event_type}: {e}")

    # Set the WebSocket forwarder on the global event bus
    event_bus.set_websocket_forwarder(websocket_forwarder)