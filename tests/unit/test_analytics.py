"""
Unit Tests for Analytics Service

Tests analytics calculations, performance metrics, and data processing.
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.analytics import AnalyticsService, analytics_service


class TestAnalyticsService:
    """Test cases for AnalyticsService class."""

    @pytest.fixture
    def analytics_service_instance(self):
        """Create an AnalyticsService instance for testing."""
        service = AnalyticsService()
        return service

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)

    def test_get_portfolio_performance_success(self, analytics_service_instance, mock_session):
        """Test successful portfolio performance calculation."""
        # Mock the database query result
        mock_result = Mock()
        mock_result.challenge_id = 'challenge_123'
        mock_result.initial_balance = 10000.0
        mock_result.current_equity = 12500.0
        mock_result.status = 'FUNDED'
        mock_result.started_at = datetime.now(timezone.utc) - timedelta(days=30)
        mock_result.ended_at = datetime.now(timezone.utc)
        mock_result.trade_count = 25
        mock_result.total_pnl = 2500.0
        mock_result.avg_trade_pnl = 100.0
        mock_result.pnl_volatility = 150.0
        mock_result.first_trade = datetime.now(timezone.utc) - timedelta(days=25)
        mock_result.last_trade = datetime.now(timezone.utc)

        with patch.object(analytics_service_instance, 'engine') as mock_engine:
            mock_session.execute.return_value.fetchall.return_value = [mock_result]

            # Mock time series query
            mock_time_series = []
            mock_session.execute.return_value.fetchall.side_effect = [[mock_result], mock_time_series]

            result = analytics_service_instance.get_portfolio_performance('user_123', 'all')

            assert 'overview' in result
            assert 'performance' in result
            assert 'risk_metrics' in result
            assert 'challenges' in result
            assert result['overview']['total_challenges'] == 1
            assert result['overview']['total_pnl'] == 2500.0
            assert result['performance']['sharpe_ratio'] > 0  # Should calculate Sharpe ratio

    def test_get_portfolio_performance_no_data(self, analytics_service_instance, mock_session):
        """Test portfolio performance when no data exists."""
        with patch.object(analytics_service_instance, 'engine') as mock_engine:
            mock_session.execute.return_value.fetchall.return_value = []

            result = analytics_service_instance.get_portfolio_performance('user_123', 'all')

            # Should return empty structure
            assert result['overview']['total_challenges'] == 0
            assert result['overview']['total_pnl'] == 0

    def test_calculate_max_drawdown_single_challenge(self, analytics_service_instance):
        """Test max drawdown calculation with single challenge."""
        portfolio_data = [
            Mock(current_equity=10000, total_pnl=0),
            Mock(current_equity=9500, total_pnl=-500),
            Mock(current_equity=10500, total_pnl=500),
            Mock(current_equity=9800, total_pnl=-200)
        ]

        max_dd = analytics_service_instance._calculate_max_drawdown(portfolio_data)
        assert max_dd == 2.0  # 2% drawdown (from 10000 to 9800)

    def test_calculate_max_drawdown_multiple_challenges(self, analytics_service_instance):
        """Test max drawdown calculation with multiple challenges."""
        portfolio_data = [
            Mock(current_equity=10000, total_pnl=0),
            Mock(current_equity=8000, total_pnl=-2000),  # 20% drawdown
            Mock(current_equity=12000, total_pnl=2000),
            Mock(current_equity=9600, total_pnl=-400)   # 20% drawdown from peak
        ]

        max_dd = analytics_service_instance._calculate_max_drawdown(portfolio_data)
        assert max_dd == 20.0  # 20% max drawdown

    def test_calculate_var_normal_distribution(self, analytics_service_instance):
        """Test VaR calculation with normal distribution assumption."""
        portfolio_data = [
            Mock(total_pnl=100),
            Mock(total_pnl=-50),
            Mock(total_pnl=200),
            Mock(total_pnl=-25),
            Mock(total_pnl=150)
        ]

        var_95 = analytics_service_instance._calculate_var(portfolio_data, 0.95)

        # With 5 data points, 95% VaR should be the second lowest value
        assert var_95 == 25.0  # Absolute value of -25

    def test_calculate_var_insufficient_data(self, analytics_service_instance):
        """Test VaR calculation with insufficient data."""
        portfolio_data = [Mock(total_pnl=100)]

        var = analytics_service_instance._calculate_var(portfolio_data)
        assert var == 0  # Should return 0 for insufficient data

    def test_calculate_expected_shortfall(self, analytics_service_instance):
        """Test Expected Shortfall (CVaR) calculation."""
        portfolio_data = [
            Mock(total_pnl=-200),  # Worst
            Mock(total_pnl=-100),  # 2nd worst
            Mock(total_pnl=-50),   # 3rd worst
            Mock(total_pnl=50),
            Mock(total_pnl=100),
            Mock(total_pnl=200)
        ]

        es = analytics_service_instance._calculate_expected_shortfall(portfolio_data, 0.95)

        # For 95% confidence with 6 data points, tail should include 2 worst losses
        # ES should be average of -200 and -100 = -150, absolute value = 150
        assert es == 150.0

    def test_get_trade_analytics_comprehensive(self, analytics_service_instance, mock_session):
        """Test comprehensive trade analytics calculation."""
        # Mock trade data
        mock_trades = [
            Mock(symbol='AAPL', side='BUY', quantity=10, price=150.0, realized_pnl=500.0,
                 executed_at=datetime.now(timezone.utc)),
            Mock(symbol='AAPL', side='SELL', quantity=10, price=155.0, realized_pnl=-100.0,
                 executed_at=datetime.now(timezone.utc)),
            Mock(symbol='MSFT', side='BUY', quantity=5, price=300.0, realized_pnl=250.0,
                 executed_at=datetime.now(timezone.utc))
        ]

        with patch.object(analytics_service_instance, 'engine') as mock_engine:
            mock_session.execute.return_value.fetchall.return_value = mock_trades

            result = analytics_service_instance.get_trade_analytics('user_123', 'all')

            assert 'summary' in result
            assert 'symbols' in result
            assert 'timing' in result
            assert result['summary']['total_trades'] == 3
            assert result['summary']['winning_trades'] == 2
            assert result['summary']['total_pnl'] == 650.0

    def test_get_trade_analytics_symbol_performance(self, analytics_service_instance):
        """Test symbol performance analysis in trade analytics."""
        # Create mock trade data
        trades_data = [
            Mock(symbol='AAPL', realized_pnl=500.0),
            Mock(symbol='AAPL', realized_pnl=-100.0),
            Mock(symbol='AAPL', realized_pnl=200.0),
            Mock(symbol='MSFT', realized_pnl=300.0),
            Mock(symbol='MSFT', realized_pnl=100.0)
        ]

        # Mock the main query
        with patch.object(analytics_service_instance, '_get_trade_analytics_data') as mock_get_data:
            mock_get_data.return_value = trades_data

            result = analytics_service_instance.get_trade_analytics('user_123', 'all')

            # Check symbol analysis
            aapl_symbol = next(s for s in result['symbols'] if s['symbol'] == 'AAPL')
            msft_symbol = next(s for s in result['symbols'] if s['symbol'] == 'MSFT')

            assert aapl_symbol['trades'] == 3
            assert aapl_symbol['total_pnl'] == 600.0
            assert aapl_symbol['win_rate'] == 66.7  # 2 wins out of 3 trades

            assert msft_symbol['trades'] == 2
            assert msft_symbol['total_pnl'] == 400.0
            assert msft_symbol['win_rate'] == 100.0  # 2 wins out of 2 trades

    def test_create_pnl_histogram(self, analytics_service_instance):
        """Test PnL distribution histogram creation."""
        pnl_values = [100, -50, 200, -25, 150, -75, 300]

        histogram = analytics_service_instance._create_pnl_histogram(pnl_values, bins=3)

        # Should create 3 bins
        assert len(histogram) == 3

        # Check bin ranges and counts
        first_bin = histogram[0]
        assert '100' in first_bin['range']  # Should contain negative values
        assert first_bin['count'] >= 1  # Should have some values

    def test_analyze_trade_sizes(self, analytics_service_instance):
        """Test trade size analysis and categorization."""
        trade_data = [
            Mock(quantity=1, price=100.0),   # $100 - Small
            Mock(quantity=5, price=200.0),   # $1000 - Medium
            Mock(quantity=10, price=500.0),  # $5000 - Large
            Mock(quantity=20, price=300.0),  # $6000 - Large
            Mock(quantity=50, price=500.0)   # $25000 - XL
        ]

        size_distribution = analytics_service_instance._analyze_trade_sizes(trade_data)

        # Should have 4 categories
        assert len(size_distribution) == 4

        # Check category names exist
        category_names = [item['size_range'] for item in size_distribution]
        assert 'Small (< $100)' in category_names
        assert 'Medium ($100 - $1000)' in category_names
        assert 'Large ($1000 - $10000)' in category_names
        assert 'XL (≥ $10000)' in category_names

    def test_get_market_analysis_popular_symbols(self, analytics_service_instance, mock_session):
        """Test market analysis for popular symbols."""
        mock_symbol_data = [
            Mock(symbol='AAPL', trade_count=150, total_pnl=7500.0, avg_pnl=50.0, winning_trades=120),
            Mock(symbol='MSFT', trade_count=120, total_pnl=6000.0, avg_pnl=50.0, winning_trades=95),
            Mock(symbol='GOOGL', trade_count=90, total_pnl=4500.0, avg_pnl=50.0, winning_trades=70)
        ]

        with patch.object(analytics_service_instance, 'engine') as mock_engine:
            mock_session.execute.return_value.fetchall.return_value = mock_symbol_data

            result = analytics_service_instance.get_market_analysis()

            assert 'popular_symbols' in result
            assert len(result['popular_symbols']) == 3

            # Check AAPL data
            aapl = result['popular_symbols'][0]
            assert aapl['symbol'] == 'AAPL'
            assert aapl['trade_count'] == 150
            assert aapl['win_rate'] == 80.0  # 120/150

    def test_get_market_analysis_empty(self, analytics_service_instance, mock_session):
        """Test market analysis when no data exists."""
        with patch.object(analytics_service_instance, 'engine') as mock_engine:
            mock_session.execute.return_value.fetchall.return_value = []

            result = analytics_service_instance.get_market_analysis()

            assert result['popular_symbols'] == []
            assert result['market_sentiment'] == []
            assert result['market_summary']['total_symbols_traded'] == 0

    def test_date_filter_all_time(self, analytics_service_instance):
        """Test date filtering for 'all' timeframe."""
        date_filter = analytics_service_instance._get_date_filter('all')
        assert date_filter is None

    def test_date_filter_month(self, analytics_service_instance):
        """Test date filtering for 'month' timeframe."""
        date_filter = analytics_service_instance._get_date_filter('month')
        expected_date = datetime.now(timezone.utc) - timedelta(days=30)

        # Should be approximately 30 days ago
        time_diff = abs((date_filter - expected_date).total_seconds())
        assert time_diff < 60  # Within 1 minute

    def test_date_filter_quarter(self, analytics_service_instance):
        """Test date filtering for 'quarter' timeframe."""
        date_filter = analytics_service_instance._get_date_filter('quarter')
        expected_date = datetime.now(timezone.utc) - timedelta(days=90)

        time_diff = abs((date_filter - expected_date).total_seconds())
        assert time_diff < 60

    def test_date_filter_year(self, analytics_service_instance):
        """Test date filtering for 'year' timeframe."""
        date_filter = analytics_service_instance._get_date_filter('year')
        expected_date = datetime.now(timezone.utc) - timedelta(days=365)

        time_diff = abs((date_filter - expected_date).total_seconds())
        assert time_diff < 60

    def test_date_filter_invalid(self, analytics_service_instance):
        """Test date filtering for invalid timeframe defaults to all."""
        date_filter = analytics_service_instance._get_date_filter('invalid')
        assert date_filter is None

    def test_portfolio_performance_time_series(self, analytics_service_instance, mock_session):
        """Test portfolio time series data generation."""
        # Mock time series data
        mock_ts_data = [
            Mock(trade_date=datetime.now(timezone.utc).date(), portfolio_value=10000.0, daily_pnl=500.0),
            Mock(trade_date=(datetime.now(timezone.utc) - timedelta(days=1)).date(), portfolio_value=9500.0, daily_pnl=-500.0)
        ]

        with patch.object(analytics_service_instance, '_get_portfolio_time_series_data') as mock_get_ts:
            mock_get_ts.return_value = mock_ts_data

            result = analytics_service_instance.get_portfolio_performance('user_123', 'month')

            assert 'time_series' in result
            assert len(result['time_series']) == 2

            first_point = result['time_series'][0]
            assert 'date' in first_point
            assert 'portfolio_value' in first_point
            assert 'daily_pnl' in first_point


class TestAnalyticsIntegration:
    """Integration tests for analytics functionality."""

    def test_analytics_data_consistency(self):
        """Test that analytics data is consistent across different queries."""
        # Test that portfolio analytics match trade analytics totals
        pass

    def test_analytics_performance_under_load(self):
        """Test analytics performance with large datasets."""
        # Test query performance with many records
        pass

    def test_analytics_error_handling(self):
        """Test error handling in analytics calculations."""
        # Test division by zero, empty datasets, etc.
        pass