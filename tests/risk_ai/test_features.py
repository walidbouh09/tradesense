"""
Unit Tests for Risk Feature Engineering

Tests deterministic feature computation from trade data.
All tests use controlled data to ensure reproducible results.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from app.domains.risk_ai.features import FeatureEngineer, TradeData, FeatureSet


class TestFeatureEngineer:
    """Test feature engineering from trade data."""

    @pytest.fixture
    def sample_trades_stable(self):
        """Sample trades representing stable, profitable trader."""
        base_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        return [
            TradeData(
                trade_id="trade_1",
                symbol="EURUSD",
                side="BUY",
                quantity=Decimal("10000"),
                price=Decimal("1.0500"),
                realized_pnl=Decimal("50.00"),
                executed_at=base_time
            ),
            TradeData(
                trade_id="trade_2",
                symbol="EURUSD",
                side="SELL",
                quantity=Decimal("10000"),
                price=Decimal("1.0520"),
                realized_pnl=Decimal("75.00"),
                executed_at=base_time.replace(hour=10)
            ),
            TradeData(
                trade_id="trade_3",
                symbol="GBPUSD",
                side="BUY",
                quantity=Decimal("5000"),
                price=Decimal("1.2500"),
                realized_pnl=Decimal("-25.00"),
                executed_at=base_time.replace(hour=11)
            ),
            TradeData(
                trade_id="trade_4",
                symbol="GBPUSD",
                side="SELL",
                quantity=Decimal("5000"),
                price=Decimal("1.2520"),
                realized_pnl=Decimal("40.00"),
                executed_at=base_time.replace(hour=12)
            ),
        ]

    @pytest.fixture
    def sample_trades_volatile(self):
        """Sample trades representing volatile trader."""
        base_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        return [
            TradeData(
                trade_id="trade_1",
                symbol="EURUSD",
                side="BUY",
                quantity=Decimal("10000"),
                price=Decimal("1.0500"),
                realized_pnl=Decimal("500.00"),
                executed_at=base_time
            ),
            TradeData(
                trade_id="trade_2",
                symbol="EURUSD",
                side="SELL",
                quantity=Decimal("10000"),
                price=Decimal("1.0480"),
                realized_pnl=Decimal("-450.00"),
                executed_at=base_time.replace(hour=9, minute=30)
            ),
            TradeData(
                trade_id="trade_3",
                symbol="GBPUSD",
                side="BUY",
                quantity=Decimal("20000"),
                price=Decimal("1.2500"),
                realized_pnl=Decimal("-800.00"),
                executed_at=base_time.replace(hour=10)
            ),
        ]

    @pytest.fixture
    def challenge_started_at(self):
        """Challenge start time for testing."""
        return datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)

    def test_stable_trader_features(self, sample_trades_stable, challenge_started_at):
        """Test feature computation for stable trader."""
        features = FeatureEngineer.compute_features(
            sample_trades_stable,
            challenge_started_at
        )

        # Performance features
        assert features.avg_trade_pnl == Decimal("35.00")  # (50+75-25+40)/4
        assert features.win_rate == Decimal("75.00")  # 3 winning trades out of 4
        assert features.pnl_volatility > Decimal("0")  # Should have some volatility

        # Risk features
        assert features.max_intraday_drawdown >= Decimal("0")
        assert features.loss_streak >= 0

        # Behavioral features
        assert features.trades_per_hour > Decimal("0")
        assert features.overtrading_score >= Decimal("0")
        assert features.revenge_trading_score >= Decimal("0")

        # Metadata
        assert features.total_trades == 4
        assert features.analysis_period_hours >= Decimal("1")

    def test_volatile_trader_features(self, sample_trades_volatile, challenge_started_at):
        """Test feature computation for volatile trader."""
        features = FeatureEngineer.compute_features(
            sample_trades_volatile,
            challenge_started_at
        )

        # Should show higher volatility
        assert features.pnl_volatility > Decimal("400")  # High volatility expected

        # Should show loss streak
        assert features.loss_streak >= 1

        # Win rate should be lower
        assert features.win_rate < Decimal("50.00")

    def test_empty_trades_default_features(self, challenge_started_at):
        """Test default features when no trades available."""
        features = FeatureEngineer.compute_features([], challenge_started_at)

        assert features.total_trades == 0
        assert features.avg_trade_pnl == Decimal("0")
        assert features.win_rate == Decimal("0")
        assert features.pnl_volatility == Decimal("0")
        assert features.max_intraday_drawdown == Decimal("0")
        assert features.loss_streak == 0

    def test_single_trade_features(self, challenge_started_at):
        """Test feature computation with single trade."""
        single_trade = [
            TradeData(
                trade_id="trade_1",
                symbol="EURUSD",
                side="BUY",
                quantity=Decimal("10000"),
                price=Decimal("1.0500"),
                realized_pnl=Decimal("100.00"),
                executed_at=challenge_started_at.replace(hour=9)
            )
        ]

        features = FeatureEngineer.compute_features(single_trade, challenge_started_at)

        assert features.total_trades == 1
        assert features.avg_trade_pnl == Decimal("100.00")
        assert features.win_rate == Decimal("100.00")
        assert features.pnl_volatility == Decimal("0")  # No volatility with single trade

    def test_loss_streak_calculation(self):
        """Test loss streak computation."""
        base_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Trades: win, loss, loss, win
        trades = [
            TradeData("t1", "EURUSD", "BUY", Decimal("10000"), Decimal("1.05"), Decimal("10"), base_time),
            TradeData("t2", "EURUSD", "SELL", Decimal("10000"), Decimal("1.05"), Decimal("-5"), base_time.replace(minute=1)),
            TradeData("t3", "EURUSD", "BUY", Decimal("10000"), Decimal("1.05"), Decimal("-15"), base_time.replace(minute=2)),
            TradeData("t4", "EURUSD", "SELL", Decimal("10000"), Decimal("1.05"), Decimal("20"), base_time.replace(minute=3)),
        ]

        features = FeatureEngineer.compute_features(trades, base_time)

        # Loss streak should be 2 (the last two trades before the win)
        assert features.loss_streak == 2

    def test_overtrading_calculation(self):
        """Test overtrading score computation."""
        base_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Many trades with low win rate = high overtrading
        trades = []
        for i in range(20):  # 20 trades in 2 hours = 10 trades/hour
            pnl = Decimal("1") if i % 5 == 0 else Decimal("-2")  # 20% win rate
            trades.append(TradeData(
                f"t{i}",
                "EURUSD",
                "BUY" if i % 2 == 0 else "SELL",
                Decimal("1000"),
                Decimal("1.05"),
                pnl,
                base_time.replace(minute=i)
            ))

        features = FeatureEngineer.compute_features(trades, base_time)

        # Should have high overtrading score due to frequency + low win rate
        assert features.overtrading_score > Decimal("50")
        assert features.trades_per_hour > Decimal("8")  # ~10 trades/hour

    def test_revenge_trading_calculation(self):
        """Test revenge trading pattern detection."""
        base_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Loss followed by larger position (revenge trading)
        trades = [
            TradeData("t1", "EURUSD", "BUY", Decimal("10000"), Decimal("1.05"), Decimal("-100"), base_time),
            TradeData("t2", "EURUSD", "SELL", Decimal("15000"), Decimal("1.05"), Decimal("50"), base_time.replace(minute=5)),  # 50% larger position
        ]

        features = FeatureEngineer.compute_features(trades, base_time)

        # Should detect revenge trading pattern
        assert features.revenge_trading_score > Decimal("0")

    def test_intraday_drawdown_calculation(self):
        """Test intraday drawdown computation."""
        base_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Simulate intraday equity movement
        trades = [
            # Day 1: Start 10000 -> 10100 -> 10050 -> 10080
            TradeData("t1", "EURUSD", "BUY", Decimal("10000"), Decimal("1.05"), Decimal("100"), base_time),
            TradeData("t2", "EURUSD", "SELL", Decimal("10000"), Decimal("1.05"), Decimal("-50"), base_time.replace(hour=10)),
            TradeData("t3", "EURUSD", "BUY", Decimal("10000"), Decimal("1.05"), Decimal("30"), base_time.replace(hour=11)),
        ]

        features = FeatureEngineer.compute_features(trades, base_time)

        # Max drawdown should be calculated from peak to trough
        # Peak: 10100, Trough: 10050, Drawdown: 50/10100 ≈ 0.50%
        expected_drawdown = Decimal("0.50")
        assert abs(features.max_intraday_drawdown - expected_drawdown) < Decimal("0.01")

    def test_analysis_period_calculation(self, challenge_started_at):
        """Test analysis period calculation."""
        # Trades spanning 4 hours
        trades = [
            TradeData("t1", "EURUSD", "BUY", Decimal("1000"), Decimal("1.05"), Decimal("10"),
                     challenge_started_at.replace(hour=9)),
            TradeData("t2", "EURUSD", "SELL", Decimal("1000"), Decimal("1.05"), Decimal("5"),
                     challenge_started_at.replace(hour=13)),
        ]

        features = FeatureEngineer.compute_features(trades, challenge_started_at)

        # Should be approximately 4 hours
        assert Decimal("3.9") <= features.analysis_period_hours <= Decimal("4.1")

    def test_feature_bounds(self, sample_trades_stable, challenge_started_at):
        """Test that all features are within expected bounds."""
        features = FeatureEngineer.compute_features(sample_trades_stable, challenge_started_at)

        # Win rate should be 0-100
        assert Decimal("0") <= features.win_rate <= Decimal("100")

        # Overtrading score should be 0-100
        assert Decimal("0") <= features.overtrading_score <= Decimal("100")

        # Revenge trading score should be 0-100
        assert Decimal("0") <= features.revenge_trading_score <= Decimal("100")

        # Drawdown should be non-negative
        assert features.max_intraday_drawdown >= Decimal("0")

        # Loss streak should be non-negative integer
        assert features.loss_streak >= 0
        assert isinstance(features.loss_streak, int)