"""
Shared test fixtures and configuration for TradeSense AI test suite.
"""

import pytest
import os
from unittest.mock import Mock
from flask import Flask
from app.main import create_app
from datetime import datetime, timezone


@pytest.fixture(scope='session')
def app():
    """Create and configure test application."""
    # Set test environment
    os.environ['ENV'] = 'test'
    os.environ['DATABASE_URL'] = 'postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense_test'
    os.environ['SECRET_KEY'] = 'test_secret_key_not_for_production'

    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    return app


@pytest.fixture(scope='session')
def client(app):
    """Create test client for API testing."""
    return app.test_client()


@pytest.fixture
def auth_headers():
    """Mock JWT authentication headers for API tests."""
    # In a real implementation, this would generate a valid JWT token
    # For testing, we return mock headers
    return {'Authorization': 'Bearer mock_jwt_token_for_testing'}


@pytest.fixture
def admin_auth_headers():
    """Mock admin JWT authentication headers."""
    return {'Authorization': 'Bearer mock_admin_jwt_token_for_testing'}


@pytest.fixture
def mock_user():
    """Create mock user data for testing."""
    return {
        'id': '550e8400-e29b-41d4-a716-446655440000',
        'email': 'test@example.com',
        'role': 'USER',
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc)
    }


@pytest.fixture
def mock_challenge(mock_user):
    """Create mock challenge data for testing."""
    return {
        'id': '550e8400-e29b-41d4-a716-446655440001',
        'user_id': mock_user['id'],
        'status': 'ACTIVE',
        'initial_balance': 10000.00,
        'current_equity': 10500.00,
        'created_at': datetime.now(timezone.utc),
        'started_at': datetime.now(timezone.utc)
    }


@pytest.fixture
def mock_trade(mock_challenge):
    """Create mock trade data for testing."""
    return {
        'id': '550e8400-e29b-41d4-a716-446655440002',
        'challenge_id': mock_challenge['id'],
        'symbol': 'AAPL',
        'side': 'BUY',
        'quantity': 10,
        'price': 150.00,
        'executed_at': datetime.now(timezone.utc)
    }


@pytest.fixture
def mock_payment_data(mock_user, mock_challenge):
    """Create mock payment data for testing."""
    return {
        'user_id': mock_user['id'],
        'challenge_id': mock_challenge['id'],
        'amount': 9900,  # $99.00 in cents
        'currency': 'usd',
        'status': 'completed',
        'payment_intent_id': 'pi_mock_test_id'
    }


@pytest.fixture
def mock_analytics_data():
    """Create mock analytics data for testing."""
    return {
        'portfolio_value': 10500.00,
        'total_pnl': 500.00,
        'win_rate': 65.5,
        'total_trades': 25,
        'sharpe_ratio': 1.23,
        'max_drawdown': -8.5
    }


@pytest.fixture
def mock_market_data():
    """Create mock market data for testing."""
    return {
        'AAPL': {
            'current_price': 150.25,
            'previous_close': 149.80,
            'change': 0.45,
            'change_percent': 0.30,
            'volume': 45678900
        },
        'BCP.MA': {
            'current_price': 285.50,
            'previous_close': 283.20,
            'change': 2.30,
            'change_percent': 0.81,
            'volume': 123456
        },
        'MSFT': {
            'current_price': 305.75,
            'previous_close': 304.90,
            'change': 0.85,
            'change_percent': 0.28,
            'volume': 23456789
        }
    }


@pytest.fixture
def mock_stripe_payment_intent():
    """Create mock Stripe PaymentIntent for testing."""
    mock_intent = Mock()
    mock_intent.id = 'pi_mock_test_id'
    mock_intent.client_secret = 'pi_secret_mock'
    mock_intent.amount = 9900
    mock_intent.currency = 'usd'
    mock_intent.status = 'succeeded'
    mock_intent.metadata = {
        'challenge_id': 'challenge_123',
        'user_id': 'user_456',
        'challenge_type': 'starter'
    }
    return mock_intent


@pytest.fixture
def mock_stripe_error():
    """Create mock Stripe error for testing."""
    from stripe.error import CardError
    return CardError("Your card was declined", "card_declined", "400")


@pytest.fixture(autouse=True)
def mock_external_apis():
    """Automatically mock external API calls for all tests."""
    with pytest.mock.patch('app.market_data.market_data.get_stock_price') as mock_price, \
         pytest.mock.patch('app.notifications.notification_service.send_email') as mock_email:

        # Mock market data
        mock_price.side_effect = lambda symbol: {
            'AAPL': (150.25, 149.80),
            'BCP.MA': (285.50, 283.20),
            'MSFT': (305.75, 304.90)
        }.get(symbol, (None, None))

        # Mock email sending
        mock_email.return_value = True

        yield


@pytest.fixture
def clean_database(app):
    """Ensure clean database state for integration tests."""
    # This fixture would clean/reset the test database
    # Implementation depends on your database setup
    yield
    # Cleanup after test


# Custom pytest markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as a security test"
    )
    config.addinivalue_line(
        "markers", "api: mark test as an API endpoint test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Test data factories
def create_test_user(**overrides):
    """Factory function to create test user data."""
    base_user = {
        'id': '550e8400-e29b-41d4-a716-446655440000',
        'email': 'test@example.com',
        'password_hash': 'hashed_password',
        'role': 'USER',
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc),
        'deleted_at': None
    }
    base_user.update(overrides)
    return base_user


def create_test_challenge(user_id=None, **overrides):
    """Factory function to create test challenge data."""
    base_challenge = {
        'id': '550e8400-e29b-41d4-a716-446655440001',
        'user_id': user_id or '550e8400-e29b-41d4-a716-446655440000',
        'status': 'ACTIVE',
        'initial_balance': 10000.00,
        'current_equity': 10500.00,
        'daily_start_equity': 10000.00,
        'max_equity_ever': 11000.00,
        'started_at': datetime.now(timezone.utc),
        'ended_at': None,
        'last_trade_at': datetime.now(timezone.utc),
        'created_at': datetime.now(timezone.utc)
    }
    base_challenge.update(overrides)
    return base_challenge


def create_test_trade(challenge_id=None, **overrides):
    """Factory function to create test trade data."""
    base_trade = {
        'id': '550e8400-e29b-41d4-a716-446655440002',
        'challenge_id': challenge_id or '550e8400-e29b-41d4-a716-446655440001',
        'symbol': 'AAPL',
        'side': 'BUY',
        'quantity': 10,
        'price': 150.00,
        'realized_pnl': 0.00,  # Will be calculated
        'executed_at': datetime.now(timezone.utc),
        'created_at': datetime.now(timezone.utc)
    }
    base_trade.update(overrides)
    return base_trade


# Performance testing utilities
def time_test_execution(func):
    """Decorator to time test execution."""
    import time
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"Test {func.__name__} executed in {execution_time:.4f} seconds")
        return result
    return wrapper


# Database test utilities
def count_database_records(table_name, session):
    """Count records in a database table."""
    from sqlalchemy import text
    result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).fetchone()
    return result[0] if result else 0


def clean_table(table_name, session):
    """Clean all records from a database table."""
    from sqlalchemy import text
    session.execute(text(f"DELETE FROM {table_name}"))
    session.commit()