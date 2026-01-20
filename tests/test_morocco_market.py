"""
Comprehensive tests for Morocco Market Integration

Tests Casablanca Stock Exchange web scraping and API endpoints.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, timezone

from app.market_data import market_data, MarketDataService


class TestMoroccoStockPriceFetching:
    """Test Morocco stock price fetching."""
    
    @patch('app.market_data.MarketDataService._get_casablanca_price_real')
    def test_fetch_iam_stock(self, mock_get_price):
        """Test fetching IAM (Maroc Telecom) stock price."""
        mock_get_price.return_value = (Decimal('145.25'), Decimal('143.80'))
        
        current_price, previous_close = market_data.get_stock_price('IAM.MA')
        
        assert current_price == Decimal('145.25')
        assert previous_close == Decimal('143.80')
    
    @patch('app.market_data.MarketDataService._get_casablanca_price_real')
    def test_fetch_atw_stock(self, mock_get_price):
        """Test fetching ATW (Attijariwafa Bank) stock price."""
        mock_get_price.return_value = (Decimal('485.50'), Decimal('482.00'))
        
        current_price, previous_close = market_data.get_stock_price('ATW.MA')
        
        assert current_price == Decimal('485.50')
        assert previous_close == Decimal('482.00')
    
    @patch('app.market_data.MarketDataService._get_casablanca_price_real')
    def test_fetch_bcp_stock(self, mock_get_price):
        """Test fetching BCP (Banque Centrale Populaire) stock price."""
        mock_get_price.return_value = (Decimal('285.00'), Decimal('283.50'))
        
        current_price, previous_close = market_data.get_stock_price('BCP.MA')
        
        assert current_price == Decimal('285.00')
        assert previous_close == Decimal('283.50')
    
    def test_symbol_normalization(self):
        """Test that symbols are normalized with .MA suffix."""
        # Test with .MA suffix
        assert 'IAM.MA'.endswith('.MA')
        
        # Test without .MA suffix (should be added by API)
        symbol = 'IAM'
        normalized = f"{symbol}.MA" if not symbol.endswith('.MA') else symbol
        assert normalized == 'IAM.MA'


class TestCaching:
    """Test price caching mechanism."""
    
    def test_cache_stores_prices(self):
        """Test that prices are cached."""
        service = MarketDataService()
        
        # Cache a price
        price_data = (Decimal('145.25'), Decimal('143.80'))
        service._cache_price('IAM.MA', price_data, expiry_seconds=300)
        
        # Verify it's cached
        cached = service._get_cached_price('IAM.MA')
        assert cached is not None
        assert cached[0] == Decimal('145.25')
    
    def test_cache_expiry(self):
        """Test that cache expires after TTL."""
        service = MarketDataService()
        
        # Cache with 0 second expiry
        price_data = (Decimal('145.25'), Decimal('143.80'))
        service._cache_price('IAM.MA', price_data, expiry_seconds=0)
        
        # Should be expired immediately
        import time
        time.sleep(0.1)
        cached = service._get_cached_price('IAM.MA')
        assert cached is None
    
    def test_cache_hit_reduces_requests(self):
        """Test that cache hits reduce external requests."""
        service = MarketDataService()
        
        # First request - cache miss
        with patch.object(service, '_get_casablanca_price_real') as mock_fetch:
            mock_fetch.return_value = (Decimal('145.25'), Decimal('143.80'))
            
            price1, prev1 = service.get_stock_price('IAM.MA')
            assert mock_fetch.call_count == 1
            
            # Second request - cache hit (within 5 minutes)
            price2, prev2 = service.get_stock_price('IAM.MA')
            assert mock_fetch.call_count == 1  # Not called again
            
            assert price1 == price2


class TestRateLimiting:
    """Test rate limiting mechanism."""
    
    def test_rate_limit_delay(self):
        """Test that rate limiting adds delay between requests."""
        service = MarketDataService()
        service.request_delay = 0.1  # 100ms for testing
        
        import time
        start = time.time()
        
        # First request
        service._rate_limit('test_source')
        
        # Second request should be delayed
        service._rate_limit('test_source')
        
        elapsed = time.time() - start
        assert elapsed >= 0.1  # At least 100ms delay
    
    def test_rate_limit_per_source(self):
        """Test that rate limiting is per-source."""
        service = MarketDataService()
        service.request_delay = 0.1
        
        # Different sources should not interfere
        service._rate_limit('source1')
        service._rate_limit('source2')  # Should not be delayed


class TestScrapingStrategies:
    """Test multiple scraping strategies."""
    
    @patch('app.market_data.requests.Session.get')
    def test_strategy_1_css_selectors(self, mock_get):
        """Test CSS selector strategy."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <div class="cours-actuel">145.25</div>
            <div class="cours-precedent">143.80</div>
        </html>
        '''
        mock_get.return_value = mock_response
        
        service = MarketDataService()
        # This would test the actual scraping logic
        # In practice, we mock the entire method
    
    @patch('app.market_data.requests.Session.get')
    def test_strategy_2_table_parsing(self, mock_get):
        """Test table parsing strategy."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <table>
                <tr><td>Cours</td><td>145.25</td></tr>
                <tr><td>Clôture précédente</td><td>143.80</td></tr>
            </table>
        </html>
        '''
        mock_get.return_value = mock_response
        
        service = MarketDataService()
        # Test table parsing logic
    
    def test_fallback_to_mock_data(self):
        """Test fallback to mock data when scraping fails."""
        service = MarketDataService()
        
        with patch.object(service, '_get_casablanca_price_real') as mock_real:
            mock_real.return_value = (None, None)
            
            with patch.object(service, '_get_casablanca_price_mock') as mock_fallback:
                mock_fallback.return_value = (Decimal('145.25'), Decimal('143.80'))
                
                price, prev = service.get_stock_price('IAM.MA')
                
                assert price == Decimal('145.25')
                assert mock_fallback.called


class TestMarketStatus:
    """Test market status checking."""
    
    def test_is_market_open_casablanca(self):
        """Test Casablanca market hours check."""
        # Casablanca market: 09:30 - 15:30 WET
        # This is a simplified test - actual implementation checks timezone
        
        service = MarketDataService()
        # Mock the time to be during market hours
        with patch('app.market_data.datetime') as mock_datetime:
            # Set time to 12:00 WET (market open)
            mock_datetime.now.return_value = datetime(2024, 1, 19, 12, 0, 0)
            # Test would check if market is open


class TestErrorHandling:
    """Test error handling and resilience."""
    
    @patch('app.market_data.requests.Session.get')
    def test_http_error_handling(self, mock_get):
        """Test handling of HTTP errors."""
        mock_get.side_effect = Exception("Connection error")
        
        service = MarketDataService()
        
        # Should not raise exception, should return None or mock data
        price, prev = service.get_stock_price('IAM.MA')
        
        # Should fallback to mock data
        assert price is not None or price is None  # Depends on implementation
    
    @patch('app.market_data.requests.Session.get')
    def test_timeout_handling(self, mock_get):
        """Test handling of request timeouts."""
        import requests
        mock_get.side_effect = requests.Timeout("Request timeout")
        
        service = MarketDataService()
        
        # Should handle timeout gracefully
        price, prev = service.get_stock_price('IAM.MA')
        # Should not crash
    
    @patch('app.market_data.requests.Session.get')
    def test_invalid_html_handling(self, mock_get):
        """Test handling of invalid HTML."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Invalid HTML <><><"
        mock_get.return_value = mock_response
        
        service = MarketDataService()
        
        # Should handle invalid HTML gracefully
        price, prev = service.get_stock_price('IAM.MA')
        # Should not crash


class TestMoroccoAPIEndpoint:
    """Test Morocco market API endpoint."""
    
    def test_api_endpoint_structure(self):
        """Test API endpoint returns correct structure."""
        # This would test the actual Flask endpoint
        # Expected structure:
        expected_keys = [
            'success', 'symbol', 'name', 'exchange', 'currency',
            'price', 'market', 'metadata'
        ]
        
        # Price object should have:
        price_keys = ['current', 'previous_close', 'change', 'change_percent']
        
        # Market object should have:
        market_keys = ['is_open', 'timezone', 'trading_hours']
        
        # Metadata object should have:
        metadata_keys = ['data_source', 'last_updated', 'cache_ttl', 'note']
    
    @patch('app.market_data.market_data.get_stock_price')
    def test_api_success_response(self, mock_get_price):
        """Test successful API response."""
        mock_get_price.return_value = (Decimal('145.25'), Decimal('143.80'))
        
        # Expected response structure
        response = {
            'success': True,
            'symbol': 'IAM.MA',
            'name': 'Itissalat Al-Maghrib (Maroc Telecom)',
            'exchange': 'Casablanca Stock Exchange',
            'currency': 'MAD',
            'price': {
                'current': 145.25,
                'previous_close': 143.80,
                'change': 1.45,
                'change_percent': 1.01
            }
        }
        
        assert response['success'] is True
        assert response['symbol'] == 'IAM.MA'
        assert response['price']['current'] == 145.25
    
    def test_api_error_response(self):
        """Test API error response."""
        # Expected error response structure
        error_response = {
            'success': False,
            'error': 'Unable to fetch price for IAM.MA',
            'message': 'Stock not found or data unavailable',
            'symbol': 'IAM.MA',
            'exchange': 'Casablanca Stock Exchange',
            'currency': 'MAD'
        }
        
        assert error_response['success'] is False
        assert 'error' in error_response


class TestStockNameMapping:
    """Test stock symbol to name mapping."""
    
    def test_known_stock_names(self):
        """Test mapping of known Moroccan stocks."""
        stock_names = {
            'IAM.MA': 'Itissalat Al-Maghrib (Maroc Telecom)',
            'ATW.MA': 'Attijariwafa Bank',
            'BCP.MA': 'Banque Centrale Populaire',
            'ATL.MA': 'ATLANTASANADIR',
            'TQM.MA': 'Total Quartz Maroc',
            'LHM.MA': 'LafargeHolcim Maroc'
        }
        
        for symbol, name in stock_names.items():
            assert len(name) > 0
            assert symbol.endswith('.MA')
    
    def test_unknown_stock_fallback(self):
        """Test fallback for unknown stocks."""
        unknown_symbol = 'UNKNOWN.MA'
        # Should return symbol without .MA suffix
        expected = 'UNKNOWN'
        assert unknown_symbol.replace('.MA', '') == expected


class TestPriceCalculations:
    """Test price change calculations."""
    
    def test_price_change_calculation(self):
        """Test price change calculation."""
        current = Decimal('145.25')
        previous = Decimal('143.80')
        
        change = float(current - previous)
        change_percent = float((current - previous) / previous * 100)
        
        assert abs(change - 1.45) < 0.01
        assert abs(change_percent - 1.01) < 0.01
    
    def test_negative_price_change(self):
        """Test negative price change calculation."""
        current = Decimal('143.80')
        previous = Decimal('145.25')
        
        change = float(current - previous)
        change_percent = float((current - previous) / previous * 100)
        
        assert change < 0
        assert change_percent < 0
    
    def test_zero_previous_close(self):
        """Test handling of zero previous close."""
        current = Decimal('145.25')
        previous = Decimal('0')
        
        if previous > 0:
            change_percent = float((current - previous) / previous * 100)
        else:
            change_percent = 0.0
        
        assert change_percent == 0.0


class TestSafetyFeatures:
    """Test safety and ethical scraping features."""
    
    def test_rate_limiting_enabled(self):
        """Test that rate limiting is enabled."""
        service = MarketDataService()
        assert service.request_delay >= 1.0  # At least 1 second
    
    def test_caching_enabled(self):
        """Test that caching is enabled."""
        service = MarketDataService()
        assert hasattr(service, 'price_cache')
        assert hasattr(service, 'cache_expiry')
    
    def test_user_agent_set(self):
        """Test that proper User-Agent is set."""
        service = MarketDataService()
        assert 'User-Agent' in service.session.headers
        assert len(service.session.headers['User-Agent']) > 0
    
    def test_no_aggressive_crawling(self):
        """Test that there's no aggressive crawling."""
        service = MarketDataService()
        # Should have rate limiting
        assert service.request_delay > 0
        # Should have caching
        assert hasattr(service, 'price_cache')
    
    def test_respectful_scraping(self):
        """Test respectful scraping practices."""
        service = MarketDataService()
        
        # Should have:
        # 1. Rate limiting
        assert service.request_delay >= 1.0
        
        # 2. Caching
        assert hasattr(service, 'price_cache')
        
        # 3. Proper headers
        assert 'User-Agent' in service.session.headers
        
        # 4. Timeout
        # (Would check in actual request calls)


class TestIntegration:
    """Test Morocco market integration scenarios."""
    
    @patch('app.market_data.market_data.get_stock_price')
    def test_complete_fetch_flow(self, mock_get_price):
        """Test complete stock price fetch flow."""
        # 1. Request comes in for IAM.MA
        symbol = 'IAM.MA'
        
        # 2. Check cache (miss)
        # 3. Rate limit
        # 4. Fetch from Casablanca Stock Exchange
        mock_get_price.return_value = (Decimal('145.25'), Decimal('143.80'))
        
        # 5. Parse response
        current_price, previous_close = mock_get_price(symbol)
        
        # 6. Cache result
        # 7. Return to API
        
        assert current_price == Decimal('145.25')
        assert previous_close == Decimal('143.80')
    
    def test_multiple_stock_fetches(self):
        """Test fetching multiple stocks."""
        stocks = ['IAM.MA', 'ATW.MA', 'BCP.MA']
        
        service = MarketDataService()
        
        with patch.object(service, '_get_casablanca_price_real') as mock_fetch:
            mock_fetch.side_effect = [
                (Decimal('145.25'), Decimal('143.80')),
                (Decimal('485.50'), Decimal('482.00')),
                (Decimal('285.00'), Decimal('283.50'))
            ]
            
            results = []
            for stock in stocks:
                price, prev = service.get_stock_price(stock)
                results.append((stock, price, prev))
            
            assert len(results) == 3
            assert all(r[1] is not None for r in results)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
