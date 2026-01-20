"""
API Documentation Endpoints

Provides Swagger/OpenAPI documentation for the TradeSense AI API.
"""

from flask import jsonify, current_app
from . import api_bp


@api_bp.route('/docs', methods=['GET'])
def get_api_docs():
    """
    Get complete API documentation in OpenAPI 3.0 format.

    Returns comprehensive API specification for all endpoints.
    """
    api_docs = {
        "openapi": "3.0.3",
        "info": {
            "title": "TradeSense AI API",
            "description": """
            **TradeSense AI** is a comprehensive prop trading platform that combines AI-powered risk management,
            gamification, and real-time market data to provide traders with an unparalleled trading experience.

            ## Key Features
            - **AI Risk Intelligence**: Advanced risk scoring and monitoring
            - **Real-time Trading**: Live market data from Yahoo Finance and Casablanca Stock Exchange
            - **Gamification**: Achievements, badges, and leaderboards
            - **Comprehensive Analytics**: Detailed performance metrics and insights
            - **Secure Payments**: Stripe integration for challenge purchases
            - **Admin Dashboard**: Complete platform management tools

            ## Authentication
            All API endpoints require JWT authentication. Include the JWT token in the Authorization header:
            ```
            Authorization: Bearer <your_jwt_token>
            ```

            ## Rate Limiting
            - 1000 requests per hour for regular users
            - 10000 requests per hour for premium users
            - Admin endpoints: 5000 requests per hour

            ## Error Responses
            All endpoints return standardized error responses:
            ```json
            {
                "error": "Error description",
                "code": "ERROR_CODE",
                "timestamp": "2024-01-18T10:30:00Z"
            }
            ```
            """,
            "version": "1.0.0",
            "contact": {
                "name": "TradeSense AI Support",
                "email": "support@tradesense.ai",
                "url": "https://tradesense.ai/support"
            },
            "license": {
                "name": "Proprietary",
                "url": "https://tradesense.ai/license"
            }
        },
        "servers": [
            {
                "url": "https://api.tradesense.ai/v1",
                "description": "Production server"
            },
            {
                "url": "http://localhost:8000/api",
                "description": "Development server"
            }
        ],
        "security": [
            {
                "bearerAuth": []
            }
        ],
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                }
            },
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "email": {"type": "string", "format": "email"},
                        "role": {"type": "string", "enum": ["USER", "ADMIN", "SUPERADMIN"]},
                        "created_at": {"type": "string", "format": "date-time"},
                        "stats": {
                            "type": "object",
                            "properties": {
                                "total_challenges": {"type": "integer"},
                                "funded_challenges": {"type": "integer"},
                                "total_trades": {"type": "integer"},
                                "total_pnl": {"type": "number"}
                            }
                        }
                    }
                },
                "Challenge": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "user_id": {"type": "string", "format": "uuid"},
                        "status": {"type": "string", "enum": ["PENDING", "ACTIVE", "FAILED", "FUNDED"]},
                        "initial_balance": {"type": "number", "minimum": 0},
                        "current_equity": {"type": "number", "minimum": 0},
                        "created_at": {"type": "string", "format": "date-time"}
                    }
                },
                "Trade": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "challenge_id": {"type": "string", "format": "uuid"},
                        "symbol": {"type": "string"},
                        "side": {"type": "string", "enum": ["BUY", "SELL"]},
                        "quantity": {"type": "number", "minimum": 0},
                        "price": {"type": "number", "minimum": 0},
                        "executed_at": {"type": "string", "format": "date-time"}
                    }
                },
                "Error": {
                    "type": "object",
                    "properties": {
                        "error": {"type": "string"},
                        "code": {"type": "string"},
                        "timestamp": {"type": "string", "format": "date-time"}
                    }
                }
            }
        },
        "paths": {
            # Health Check
            "/health": {
                "get": {
                    "summary": "Health Check",
                    "description": "Check API and system health status",
                    "responses": {
                        "200": {
                            "description": "System is healthy",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string", "enum": ["healthy"]},
                                            "timestamp": {"type": "string", "format": "date-time"},
                                            "version": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },

            # Authentication
            "/auth/login": {
                "post": {
                    "summary": "User Login",
                    "description": "Authenticate user and return JWT token",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["email", "password"],
                                    "properties": {
                                        "email": {"type": "string", "format": "email"},
                                        "password": {"type": "string", "minLength": 8}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Login successful",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "access_token": {"type": "string"},
                                            "token_type": {"type": "string", "enum": ["bearer"]},
                                            "expires_in": {"type": "integer"}
                                        }
                                    }
                                }
                            }
                        },
                        "401": {"description": "Invalid credentials"}
                    }
                }
            },
            "/auth/register": {
                "post": {
                    "summary": "User Registration",
                    "description": "Register a new user account",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["email", "password"],
                                    "properties": {
                                        "email": {"type": "string", "format": "email"},
                                        "password": {"type": "string", "minLength": 8}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {"description": "User registered successfully"},
                        "400": {"description": "Validation error"}
                    }
                }
            },

            # Challenges
            "/challenges": {
                "get": {
                    "summary": "List User Challenges",
                    "description": "Get all challenges for the authenticated user",
                    "parameters": [
                        {
                            "name": "status",
                            "in": "query",
                            "schema": {"type": "string", "enum": ["PENDING", "ACTIVE", "FAILED", "FUNDED"]}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "List of challenges",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "challenges": {
                                                "type": "array",
                                                "items": {"$ref": "#/components/schemas/Challenge"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "post": {
                    "summary": "Create Challenge",
                    "description": "Create a new trading challenge",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["initial_balance"],
                                    "properties": {
                                        "initial_balance": {"type": "number", "minimum": 100}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Challenge created",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Challenge"}
                                }
                            }
                        }
                    }
                }
            },

            # Trades
            "/trades": {
                "post": {
                    "summary": "Execute Trade",
                    "description": "Execute a trade within an active challenge",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["challenge_id", "symbol", "side", "quantity", "price"],
                                    "properties": {
                                        "challenge_id": {"type": "string", "format": "uuid"},
                                        "symbol": {"type": "string"},
                                        "side": {"type": "string", "enum": ["BUY", "SELL"]},
                                        "quantity": {"type": "number", "minimum": 0},
                                        "price": {"type": "number", "minimum": 0}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Trade executed",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Trade"}
                                }
                            }
                        },
                        "400": {"description": "Invalid trade parameters"}
                    }
                }
            },

            # Payments
            "/payments/create-intent": {
                "post": {
                    "summary": "Create Payment Intent",
                    "description": "Create a Stripe PaymentIntent for challenge purchase",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["challenge_id", "user_id"],
                                    "properties": {
                                        "challenge_id": {"type": "string", "format": "uuid"},
                                        "user_id": {"type": "string", "format": "uuid"},
                                        "challenge_type": {"type": "string", "enum": ["starter", "professional", "expert", "master"]}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Payment intent created",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "client_secret": {"type": "string"},
                                            "payment_intent_id": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },

            # Leaderboard
            "/leaderboard/global": {
                "get": {
                    "summary": "Global Leaderboard",
                    "description": "Get ranked list of top traders",
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50}
                        },
                        {
                            "name": "timeframe",
                            "in": "query",
                            "schema": {"type": "string", "enum": ["all", "month", "week", "today"], "default": "all"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Leaderboard data",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "leaderboard": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "rank": {"type": "integer"},
                                                        "user_id": {"type": "string"},
                                                        "stats": {
                                                            "type": "object",
                                                            "properties": {
                                                                "total_pnl": {"type": "number"},
                                                                "success_rate": {"type": "number"}
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },

            # Analytics
            "/analytics/portfolio/{user_id}": {
                "get": {
                    "summary": "Portfolio Analytics",
                    "description": "Get comprehensive portfolio performance analytics",
                    "parameters": [
                        {
                            "name": "user_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"}
                        },
                        {
                            "name": "timeframe",
                            "in": "query",
                            "schema": {"type": "string", "enum": ["all", "month", "quarter", "year"], "default": "all"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Portfolio analytics",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "analytics": {
                                                "type": "object",
                                                "properties": {
                                                    "overview": {"type": "object"},
                                                    "performance": {"type": "object"},
                                                    "risk_metrics": {"type": "object"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },

            # User Profiles
            "/profiles/{user_id}": {
                "get": {
                    "summary": "User Profile",
                    "description": "Get complete user profile with statistics",
                    "parameters": [
                        {
                            "name": "user_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "User profile data",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "profile": {
                                                "type": "object",
                                                "properties": {
                                                    "trading_stats": {"type": "object"},
                                                    "achievements": {"type": "array"},
                                                    "rankings": {"type": "object"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },

            # Admin endpoints (require admin role)
            "/admin/dashboard": {
                "get": {
                    "summary": "Admin Dashboard",
                    "description": "Get comprehensive admin dashboard statistics",
                    "security": [{"bearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "Admin dashboard data",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "dashboard": {
                                                "type": "object",
                                                "properties": {
                                                    "users": {"type": "object"},
                                                    "challenges": {"type": "object"},
                                                    "financial": {"type": "object"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "403": {"description": "Admin access required"}
                    }
                }
            },

            # Market Data
            "/market/status": {
                "get": {
                    "summary": "Market Status",
                    "description": "Get current market open/closed status",
                    "responses": {
                        "200": {
                            "description": "Market status information",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "casablanca": {
                                                "type": "object",
                                                "properties": {
                                                    "open": {"type": "boolean"},
                                                    "name": {"type": "string"}
                                                }
                                            },
                                            "us": {
                                                "type": "object",
                                                "properties": {
                                                    "open": {"type": "boolean"},
                                                    "name": {"type": "string"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/market/prices": {
                "get": {
                    "summary": "Live Prices",
                    "description": "Get current prices for specified symbols",
                    "parameters": [
                        {
                            "name": "symbols",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Comma-separated list of symbols (e.g., 'AAPL,BCP.MA,MSFT')"
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Current prices data",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "prices": {
                                                "type": "object",
                                                "additionalProperties": {
                                                    "type": "object",
                                                    "properties": {
                                                        "current_price": {"type": "number"},
                                                        "previous_close": {"type": "number"},
                                                        "change": {"type": "number"},
                                                        "change_percent": {"type": "number"}
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "tags": [
            {
                "name": "Authentication",
                "description": "User authentication and authorization"
            },
            {
                "name": "Challenges",
                "description": "Trading challenge management"
            },
            {
                "name": "Trades",
                "description": "Trade execution and history"
            },
            {
                "name": "Payments",
                "description": "Payment processing and billing"
            },
            {
                "name": "Analytics",
                "description": "Performance analytics and insights"
            },
            {
                "name": "Leaderboard",
                "description": "Trader rankings and competitions"
            },
            {
                "name": "Profiles",
                "description": "User profiles and statistics"
            },
            {
                "name": "Rewards",
                "description": "Achievements and gamification"
            },
            {
                "name": "Admin",
                "description": "Administrative functions (admin only)"
            },
            {
                "name": "Market Data",
                "description": "Real-time market data and prices"
            }
        ]
    }

    return jsonify(api_docs), 200


@api_bp.route('/docs/swagger', methods=['GET'])
def get_swagger_ui():
    """
    Redirect to Swagger UI.

    In a production environment, this would serve the Swagger UI HTML.
    """
    return jsonify({
        "message": "Swagger UI would be served here in production",
        "docs_url": "/api/docs",
        "swagger_ui_url": "https://swagger.io/tools/swagger-ui/"
    }), 200


@api_bp.route('/docs/redoc', methods=['GET'])
def get_redoc():
    """
    Redirect to ReDoc documentation.

    In a production environment, this would serve the ReDoc HTML.
    """
    return jsonify({
        "message": "ReDoc would be served here in production",
        "docs_url": "/api/docs",
        "redoc_url": "https://redoc.ly/"
    }), 200


@api_bp.route('/docs/versions', methods=['GET'])
def get_api_versions():
    """
    Get API version information and changelog.
    """
    versions = {
        "current": {
            "version": "1.0.0",
            "released": "2024-01-18",
            "status": "stable",
            "changelog": [
                "Complete API redesign with OpenAPI 3.0 specification",
                "Added comprehensive analytics and insights endpoints",
                "Implemented gamification with achievements and rewards",
                "Added real-time market data integration",
                "Enhanced security with JWT authentication",
                "Added admin dashboard and management tools"
            ]
        },
        "upcoming": {
            "version": "1.1.0",
            "estimated_release": "2024-03-01",
            "features": [
                "WebSocket streaming for real-time updates",
                "Advanced backtesting capabilities",
                "Multi-asset support (crypto, forex)",
                "Social trading features",
                "Mobile app API endpoints"
            ]
        },
        "deprecated": [
            {
                "version": "0.9.0",
                "deprecated_date": "2024-01-01",
                "removal_date": "2024-04-01",
                "replacement": "1.0.0"
            }
        ]
    }

    return jsonify({
        "api_versions": versions,
        "support": {
            "current_version_support": "Full support until 2025-01-18",
            "deprecation_policy": "6 months notice for breaking changes",
            "contact": "api-support@tradesense.ai"
        }
    }), 200


@api_bp.route('/docs/usage-examples', methods=['GET'])
def get_usage_examples():
    """
    Get API usage examples and code samples.
    """
    examples = {
        "authentication": {
            "login": {
                "description": "Authenticate and get JWT token",
                "curl": """
curl -X POST http://localhost:8000/api/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{
    "email": "user@example.com",
    "password": "secure_password"
  }'
                """,
                "python": """
import requests

response = requests.post('http://localhost:8000/api/auth/login', json={
    'email': 'user@example.com',
    'password': 'secure_password'
})

token = response.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}
                """,
                "javascript": """
fetch('/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'secure_password'
  })
})
.then(res => res.json())
.then(data => {
  const token = data.access_token;
  // Store token for future requests
  localStorage.setItem('jwt_token', token);
});
                """
            }
        },
        "trading": {
            "create_challenge": {
                "description": "Create a new trading challenge",
                "curl": """
curl -X POST http://localhost:8000/api/challenges \\
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "initial_balance": 10000
  }'
                """
            },
            "execute_trade": {
                "description": "Execute a trade",
                "curl": """
curl -X POST http://localhost:8000/api/trades \\
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "challenge_id": "550e8400-e29b-41d4-a716-446655440000",
    "symbol": "AAPL",
    "side": "BUY",
    "quantity": 10,
    "price": 175.50
  }'
                """
            }
        },
        "analytics": {
            "portfolio_performance": {
                "description": "Get portfolio performance analytics",
                "curl": """
curl -X GET "http://localhost:8000/api/analytics/portfolio/550e8400-e29b-41d4-a716-446655440000?timeframe=month" \\
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
                """
            }
        },
        "market_data": {
            "get_prices": {
                "description": "Get current market prices",
                "curl": """
curl -X GET "http://localhost:8000/api/market/prices?symbols=AAPL,BCP.MA,MSFT" \\
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
                """
            }
        }
    }

    return jsonify({
        "usage_examples": examples,
        "languages": ["curl", "python", "javascript"],
        "tips": [
            "All authenticated endpoints require the Authorization header",
            "Use the health endpoint to check API availability",
            "Handle rate limiting appropriately (1000 requests/hour)",
            "All timestamps are in ISO 8601 format with UTC timezone"
        ]
    }), 200