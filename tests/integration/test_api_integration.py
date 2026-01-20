"""
Integration Tests for API Endpoints

Tests API endpoints with real database and external services.
Requires running application with test database.
"""

import pytest
import json
from unittest.mock import patch
from flask import Flask
from app.main import create_app


class TestAPIIntegration:
    """Integration tests for API endpoints."""

    @pytest.fixture
    def app(self):
        """Create test application."""
        app = create_app()
        app.config['TESTING'] = True
        app.config['DATABASE_URL'] = 'postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense_test'
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()

    @pytest.fixture
    def auth_headers(self, client):
        """Get authentication headers for API calls."""
        # Mock JWT token for testing
        return {'Authorization': 'Bearer mock_jwt_token'}

    def test_health_endpoint(self, client):
        """Test health endpoint returns correct response."""
        response = client.get('/api/health')

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'status' in data
        assert 'timestamp' in data
        assert 'version' in data
        assert data['status'] == 'healthy'

    def test_api_docs_endpoint(self, client):
        """Test API documentation endpoint."""
        response = client.get('/api/docs')

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'openapi' in data
        assert 'info' in data
        assert 'paths' in data
        assert data['info']['title'] == 'TradeSense AI API'

    def test_market_status_endpoint(self, client, auth_headers):
        """Test market status endpoint."""
        response = client.get('/api/market/status', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'casablanca' in data
        assert 'us' in data
        assert 'global' in data

        assert 'open' in data['casablanca']
        assert 'name' in data['casablanca']

    @patch('app.market_data.market_data.get_stock_price')
    def test_market_prices_endpoint(self, mock_get_price, client, auth_headers):
        """Test market prices endpoint."""
        # Mock market data response
        mock_get_price.side_effect = lambda symbol: {
            'AAPL': (150.25, 149.80),
            'BCP.MA': (285.50, 283.20),
            'MSFT': (305.75, 304.90)
        }.get(symbol, (None, None))

        response = client.get('/api/market/prices?symbols=AAPL,BCP.MA,MSFT', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'prices' in data
        assert 'AAPL' in data['prices']
        assert 'BCP.MA' in data['prices']
        assert 'MSFT' in data['prices']

        aapl_data = data['prices']['AAPL']
        assert 'current_price' in aapl_data
        assert 'change' in aapl_data
        assert 'change_percent' in aapl_data

    def test_market_prices_endpoint_no_symbols(self, client, auth_headers):
        """Test market prices endpoint without symbols parameter."""
        response = client.get('/api/market/prices', headers=auth_headers)

        # Should return 400 Bad Request
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_leaderboard_global_endpoint(self, client, auth_headers):
        """Test global leaderboard endpoint."""
        response = client.get('/api/leaderboard/global', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'leaderboard' in data
        assert 'count' in data
        assert 'timeframe' in data
        assert isinstance(data['leaderboard'], list)

    def test_leaderboard_global_with_params(self, client, auth_headers):
        """Test global leaderboard with query parameters."""
        response = client.get('/api/leaderboard/global?limit=5&timeframe=month', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['timeframe'] == 'month'
        assert data['limit'] == 5
        assert len(data['leaderboard']) <= 5

    def test_leaderboard_categories_endpoint(self, client, auth_headers):
        """Test leaderboard categories endpoint."""
        response = client.get('/api/leaderboard/categories', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'categories' in data
        assert isinstance(data['categories'], dict)

        # Should have expected categories
        expected_categories = ['most_profitable', 'highest_success_rate', 'most_active', 'best_risk_management']
        for category in expected_categories:
            assert category in data['categories']

    def test_analytics_portfolio_endpoint(self, client, auth_headers):
        """Test portfolio analytics endpoint."""
        user_id = '550e8400-e29b-41d4-a716-446655440000'  # Mock UUID

        response = client.get(f'/api/analytics/portfolio/{user_id}', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'analytics' in data
        assert 'timeframe' in data
        assert 'user_id' in data

        analytics = data['analytics']
        assert 'overview' in analytics
        assert 'performance' in analytics
        assert 'risk_metrics' in analytics

    def test_analytics_portfolio_invalid_timeframe(self, client, auth_headers):
        """Test portfolio analytics with invalid timeframe."""
        user_id = '550e8400-e29b-41d4-a716-446655440000'

        response = client.get(f'/api/analytics/portfolio/{user_id}?timeframe=invalid', headers=auth_headers)

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_analytics_trade_endpoint(self, client, auth_headers):
        """Test trade analytics endpoint."""
        user_id = '550e8400-e29b-41d4-a716-446655440000'

        response = client.get(f'/api/analytics/trades/{user_id}', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'analytics' in data
        assert 'timeframe' in data

        analytics = data['analytics']
        assert 'summary' in analytics
        assert 'symbols' in analytics
        assert 'timing' in analytics

    def test_analytics_market_endpoint(self, client, auth_headers):
        """Test market analysis endpoint."""
        response = client.get('/api/analytics/market', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'market_analysis' in data
        assert 'market_analysis' in data

        analysis = data['market_analysis']
        assert 'popular_symbols' in analysis
        assert 'market_sentiment' in analysis
        assert 'market_summary' in analysis

    def test_profiles_user_endpoint(self, client, auth_headers):
        """Test user profile endpoint."""
        user_id = '550e8400-e29b-41d4-a716-446655440000'

        response = client.get(f'/api/profiles/{user_id}', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'profile' in data
        assert 'success' in data

        profile = data['profile']
        assert 'trading_stats' in profile
        assert 'achievements' in profile
        assert 'rankings' in profile

    def test_profiles_user_achievements_endpoint(self, client, auth_headers):
        """Test user achievements endpoint."""
        user_id = '550e8400-e29b-41d4-a716-446655440000'

        response = client.get(f'/api/profiles/{user_id}/achievements', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'achievements' in data
        assert 'total_achievements' in data
        assert isinstance(data['achievements'], list)

    def test_profiles_user_activity_endpoint(self, client, auth_headers):
        """Test user activity endpoint."""
        user_id = '550e8400-e29b-41d4-a716-446655440000'

        response = client.get(f'/api/profiles/{user_id}/activity', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'activity' in data
        assert 'count' in data
        assert isinstance(data['activity'], list)

    def test_rewards_achievements_endpoint(self, client, auth_headers):
        """Test user achievements via rewards endpoint."""
        user_id = '550e8400-e29b-41d4-a716-446655440000'

        response = client.get(f'/api/rewards/achievements/{user_id}', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'rewards' in data
        assert 'success' in data

        rewards = data['rewards']
        assert 'total_points' in rewards
        assert 'achievements' in rewards
        assert 'current_badge' in rewards

    def test_rewards_leaderboard_endpoint(self, client, auth_headers):
        """Test achievements leaderboard endpoint."""
        response = client.get('/api/rewards/leaderboard', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'leaderboard' in data
        assert 'ranking_type' in data
        assert data['ranking_type'] == 'achievements'
        assert isinstance(data['leaderboard'], list)

    def test_rewards_stats_endpoint(self, client, auth_headers):
        """Test rewards statistics endpoint."""
        response = client.get('/api/rewards/stats', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'stats' in data
        assert 'success' in data

        stats = data['stats']
        assert 'total_achievements_unlocked' in stats
        assert 'total_points_awarded' in stats

    # Admin endpoints (would require admin authentication in real implementation)
    def test_admin_dashboard_endpoint(self, client):
        """Test admin dashboard endpoint (mock admin auth)."""
        # In real implementation, would need admin JWT token
        # For testing, this endpoint might return 403 without proper auth
        response = client.get('/api/admin/dashboard')

        # Either returns 403 (no auth) or 200 (if we mock admin auth)
        assert response.status_code in [200, 403]

    def test_docs_usage_examples_endpoint(self, client):
        """Test API usage examples endpoint."""
        response = client.get('/api/docs/usage-examples')

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'usage_examples' in data
        assert 'languages' in data
        assert 'tips' in data

        examples = data['usage_examples']
        assert 'authentication' in examples
        assert 'trading' in examples
        assert 'market_data' in examples

    def test_docs_versions_endpoint(self, client):
        """Test API versions endpoint."""
        response = client.get('/api/docs/versions')

        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'current' in data['api_versions']
        assert 'upcoming' in data['api_versions']
        assert 'deprecated' in data['api_versions']

        current = data['api_versions']['current']
        assert 'version' in current
        assert 'released' in current

    # Error handling tests
    def test_invalid_endpoint(self, client):
        """Test accessing invalid endpoint."""
        response = client.get('/api/invalid-endpoint')

        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """Test using wrong HTTP method."""
        response = client.post('/api/health')  # Health only allows GET

        assert response.status_code == 405

    def test_missing_authentication(self, client):
        """Test accessing authenticated endpoint without auth."""
        response = client.get('/api/challenges')

        # Should return 401 or 422 depending on JWT implementation
        assert response.status_code in [401, 422]

    # Rate limiting tests (would require rate limiting middleware)
    def test_rate_limiting(self, client):
        """Test API rate limiting."""
        # This would test that endpoints are properly rate limited
        # Implementation depends on rate limiting middleware
        pass

    # CORS tests
    def test_cors_headers(self, client):
        """Test CORS headers are present."""
        response = client.options('/api/health')

        assert 'Access-Control-Allow-Origin' in response.headers
        assert 'Access-Control-Allow-Methods' in response.headers
        assert 'Access-Control-Allow-Headers' in response.headers


class TestAPIErrorHandling:
    """Test error handling across API endpoints."""

    @pytest.fixture
    def app(self):
        """Create test application."""
        app = create_app()
        app.config['TESTING'] = True
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()

    def test_malformed_json(self, client):
        """Test handling of malformed JSON in request body."""
        response = client.post('/api/auth/login',
                             data='invalid json',
                             content_type='application/json')

        assert response.status_code == 400

    def test_invalid_uuid_format(self, client):
        """Test handling of invalid UUID format in path parameters."""
        response = client.get('/api/profiles/invalid-uuid')

        # Should handle gracefully (either 400 or 404 depending on implementation)
        assert response.status_code in [400, 404]

    def test_database_connection_error(self, client):
        """Test handling of database connection errors."""
        # This would require mocking database connection failures
        pass

    def test_external_service_timeout(self, client):
        """Test handling of external service timeouts."""
        # This would require mocking external service calls
        pass


class TestAPIPerformance:
    """Performance tests for API endpoints."""

    @pytest.fixture
    def app(self):
        """Create test application."""
        app = create_app()
        app.config['TESTING'] = True
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()

    def test_response_time_health_endpoint(self, client):
        """Test response time for health endpoint."""
        import time

        start_time = time.time()
        response = client.get('/api/health')
        end_time = time.time()

        response_time = end_time - start_time

        assert response.status_code == 200
        assert response_time < 0.5  # Should respond within 500ms

    def test_concurrent_requests(self, client):
        """Test handling of concurrent requests."""
        # This would test concurrent access to endpoints
        # Implementation would depend on testing framework capabilities
        pass

    def test_memory_usage(self, client):
        """Test memory usage during API calls."""
        # This would monitor memory usage during requests
        pass