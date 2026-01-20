"""
API Blueprint for TradeSense AI

HTTP REST endpoints for challenge management and trading operations.
Separated from WebSocket handlers for clean architecture.
"""

from flask import Blueprint

# Create the API blueprint
api_bp = Blueprint('api', __name__)

# Import routes to register them
from . import health, challenges, trades, risk, auth, payments, leaderboard, profiles, analytics, rewards, admin, docs, market