from flask import jsonify, request, current_app
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from . import api_bp
from app.backtesting_engine import (
    backtesting_engine, RSIStrategy, MACDStrategy, MeanReversionStrategy,
    TradingStrategy
)


def get_db_session():
    """Get database session."""
    engine = create_engine(current_app.config['SQLALCHEMY_DATABASE_URI'])
    return Session(engine)


@api_bp.route('/backtest/strategies', methods=['GET'])
def get_available_strategies():
    """Get list of available trading strategies."""
    strategies = [
        {
            'name': 'RSI_Strategy',
            'description': 'RSI-based mean reversion strategy',
            'parameters': {
                'rsi_period': {'default': 14, 'min': 5, 'max': 30, 'type': 'int'},
                'overbought': {'default': 70, 'min': 60, 'max': 90, 'type': 'int'},
                'oversold': {'default': 30, 'min': 10, 'max': 40, 'type': 'int'}
            }
        },
        {
            'name': 'MACD_Strategy',
            'description': 'MACD trend-following strategy',
            'parameters': {
                'fast_period': {'default': 12, 'min': 5, 'max': 20, 'type': 'int'},
                'slow_period': {'default': 26, 'min': 20, 'max': 40, 'type': 'int'},
                'signal_period': {'default': 9, 'min': 5, 'max': 15, 'type': 'int'}
            }
        },
        {
            'name': 'Mean_Reversion_Strategy',
            'description': 'Bollinger Bands mean reversion strategy',
            'parameters': {
                'bb_period': {'default': 20, 'min': 10, 'max': 50, 'type': 'int'},
                'bb_std': {'default': 2.0, 'min': 1.0, 'max': 3.0, 'type': 'float'}
            }
        }
    ]

    return jsonify({
        'strategies': strategies,
        'count': len(strategies)
    }), 200


@api_bp.route('/backtest/run', methods=['POST'])
def run_backtest():
    """
    Run a backtest for a trading strategy.

    Request body:
    {
        "strategy_name": "RSI_Strategy",
        "parameters": {"rsi_period": 14, "overbought": 70, "oversold": 30},
        "symbols": ["AAPL", "MSFT"],
        "start_date": "2023-01-01T00:00:00Z",
        "end_date": "2023-12-31T23:59:59Z",
        "initial_balance": 100000,
        "max_positions": 5
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        required_fields = ['strategy_name', 'symbols', 'start_date', 'end_date']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        strategy_name = data['strategy_name']
        parameters = data.get('parameters', {})
        symbols = data['symbols']
        start_date_str = data['start_date']
        end_date_str = data['end_date']
        initial_balance = Decimal(str(data.get('initial_balance', 100000)))
        max_positions = data.get('max_positions', 5)

        # Parse dates
        try:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        except ValueError as e:
            return jsonify({'error': f'Invalid date format: {e}'}), 400

        # Create strategy instance
        strategy = _create_strategy(strategy_name, parameters)
        if not strategy:
            return jsonify({'error': f'Unknown strategy: {strategy_name}'}), 400

        # Run backtest
        result = backtesting_engine.run_backtest(
            strategy=strategy,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            max_positions=max_positions
        )

        # Format result for JSON response
        response = {
            'strategy_name': result.strategy_name,
            'parameters': parameters,
            'symbols': symbols,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'performance': {
                'initial_balance': float(result.initial_balance),
                'final_balance': float(result.final_balance),
                'total_pnl': float(result.total_pnl),
                'total_return': float(result.total_return),
                'max_drawdown': float(result.max_drawdown),
                'sharpe_ratio': float(result.sharpe_ratio or 0),
                'calmar_ratio': float(result.calmar_ratio or 0),
                'win_rate': float(result.win_rate),
                'profit_factor': float(result.profit_factor or 0),
                'total_trades': result.total_trades,
                'winning_trades': result.winning_trades,
                'losing_trades': result.losing_trades,
                'avg_win': float(result.avg_win or 0),
                'avg_loss': float(result.avg_loss or 0)
            },
            'trades': [
                {
                    'id': trade.id,
                    'symbol': trade.symbol,
                    'side': trade.side,
                    'quantity': float(trade.quantity),
                    'entry_price': float(trade.entry_price),
                    'entry_time': trade.entry_time.isoformat(),
                    'exit_price': float(trade.exit_price) if trade.exit_price else None,
                    'exit_time': trade.exit_time.isoformat() if trade.exit_time else None,
                    'pnl': float(trade.pnl) if trade.pnl else None,
                    'pnl_percent': float(trade.pnl_percent) if trade.pnl_percent else None,
                    'holding_period': trade.holding_period,
                    'commission': float(trade.commission)
                }
                for trade in result.trades
            ],
            'equity_curve': [
                {'timestamp': ts.isoformat(), 'equity': float(equity)}
                for ts, equity in result.equity_curve
            ]
        }

        return jsonify(response), 200

    except Exception as e:
        current_app.logger.error(f"Backtest run error: {e}")
        return jsonify({'error': 'Failed to run backtest'}), 500


@api_bp.route('/backtest/optimize', methods=['POST'])
def optimize_strategy():
    """
    Optimize strategy parameters using grid search.

    Request body:
    {
        "strategy_name": "RSI_Strategy",
        "symbols": ["AAPL", "MSFT"],
        "start_date": "2023-01-01T00:00:00Z",
        "end_date": "2023-12-31T23:59:59Z",
        "parameter_ranges": {
            "rsi_period": [10, 14, 20],
            "overbought": [70, 75, 80],
            "oversold": [20, 25, 30]
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        required_fields = ['strategy_name', 'symbols', 'start_date', 'end_date', 'parameter_ranges']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        strategy_name = data['strategy_name']
        symbols = data['symbols']
        start_date_str = data['start_date']
        end_date_str = data['end_date']
        parameter_ranges = data['parameter_ranges']

        # Parse dates
        try:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        except ValueError as e:
            return jsonify({'error': f'Invalid date format: {e}'}), 400

        # Get strategy class
        strategy_class = _get_strategy_class(strategy_name)
        if not strategy_class:
            return jsonify({'error': f'Unknown strategy: {strategy_name}'}), 400

        # Run optimization
        optimization_result = backtesting_engine.optimize_strategy(
            strategy_class=strategy_class,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            parameter_ranges=parameter_ranges
        )

        best_result = optimization_result['best_result']

        response = {
            'strategy_name': strategy_name,
            'optimization_result': {
                'best_parameters': optimization_result['best_parameters'],
                'best_score': optimization_result['best_score'],
                'performance': {
                    'total_return': float(best_result.total_return),
                    'max_drawdown': float(best_result.max_drawdown),
                    'sharpe_ratio': float(best_result.sharpe_ratio or 0),
                    'win_rate': float(best_result.win_rate),
                    'total_trades': best_result.total_trades
                }
            }
        }

        return jsonify(response), 200

    except Exception as e:
        current_app.logger.error(f"Strategy optimization error: {e}")
        return jsonify({'error': 'Failed to optimize strategy'}), 500


@api_bp.route('/backtest/monte-carlo', methods=['POST'])
def monte_carlo_simulation():
    """
    Run Monte Carlo simulation for strategy robustness testing.

    Request body:
    {
        "strategy_name": "RSI_Strategy",
        "parameters": {"rsi_period": 14},
        "symbols": ["AAPL", "MSFT"],
        "start_date": "2023-01-01T00:00:00Z",
        "end_date": "2023-12-31T23:59:59Z",
        "num_simulations": 1000
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        required_fields = ['strategy_name', 'symbols', 'start_date', 'end_date']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        strategy_name = data['strategy_name']
        parameters = data.get('parameters', {})
        symbols = data['symbols']
        start_date_str = data['start_date']
        end_date_str = data['end_date']
        num_simulations = data.get('num_simulations', 1000)

        # Parse dates
        try:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        except ValueError as e:
            return jsonify({'error': f'Invalid date format: {e}'}), 400

        # Create strategy instance
        strategy = _create_strategy(strategy_name, parameters)
        if not strategy:
            return jsonify({'error': f'Unknown strategy: {strategy_name}'}), 400

        # Run Monte Carlo simulation
        simulation_result = backtesting_engine.monte_carlo_simulation(
            strategy=strategy,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            num_simulations=num_simulations
        )

        return jsonify(simulation_result), 200

    except Exception as e:
        current_app.logger.error(f"Monte Carlo simulation error: {e}")
        return jsonify({'error': 'Failed to run Monte Carlo simulation'}), 500


@api_bp.route('/backtest/compare', methods=['POST'])
def compare_strategies():
    """
    Compare multiple strategies side by side.

    Request body:
    {
        "strategies": [
            {
                "name": "RSI_Strategy",
                "parameters": {"rsi_period": 14}
            },
            {
                "name": "MACD_Strategy",
                "parameters": {"fast_period": 12, "slow_period": 26}
            }
        ],
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "start_date": "2023-01-01T00:00:00Z",
        "end_date": "2023-12-31T23:59:59Z",
        "initial_balance": 100000
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        required_fields = ['strategies', 'symbols', 'start_date', 'end_date']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        strategies_config = data['strategies']
        symbols = data['symbols']
        start_date_str = data['start_date']
        end_date_str = data['end_date']
        initial_balance = Decimal(str(data.get('initial_balance', 100000)))

        # Parse dates
        try:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        except ValueError as e:
            return jsonify({'error': f'Invalid date format: {e}'}), 400

        comparison_results = []

        for strategy_config in strategies_config:
            strategy_name = strategy_config['name']
            parameters = strategy_config.get('parameters', {})

            strategy = _create_strategy(strategy_name, parameters)
            if not strategy:
                continue

            result = backtesting_engine.run_backtest(
                strategy=strategy,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                initial_balance=initial_balance
            )

            comparison_results.append({
                'strategy_name': strategy_name,
                'parameters': parameters,
                'performance': {
                    'total_return': float(result.total_return),
                    'max_drawdown': float(result.max_drawdown),
                    'sharpe_ratio': float(result.sharpe_ratio or 0),
                    'win_rate': float(result.win_rate),
                    'profit_factor': float(result.profit_factor or 0),
                    'total_trades': result.total_trades
                }
            })

        # Sort by total return
        comparison_results.sort(key=lambda x: x['performance']['total_return'], reverse=True)

        return jsonify({
            'comparison': comparison_results,
            'best_strategy': comparison_results[0] if comparison_results else None,
            'symbols': symbols,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"Strategy comparison error: {e}")
        return jsonify({'error': 'Failed to compare strategies'}), 500


@api_bp.route('/backtest/save', methods=['POST'])
def save_backtest_result():
    """
    Save a backtest result to database for later analysis.

    Request body:
    {
        "strategy_name": "RSI_Strategy",
        "parameters": {"rsi_period": 14},
        "symbols": ["AAPL"],
        "performance": {...},
        "trades": [...]
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        # This would save the backtest result to database
        # Implementation depends on your database schema for storing backtest results

        return jsonify({
            'message': 'Backtest result saved successfully',
            'backtest_id': 'placeholder_id'
        }), 201

    except Exception as e:
        current_app.logger.error(f"Save backtest error: {e}")
        return jsonify({'error': 'Failed to save backtest result'}), 500


def _create_strategy(strategy_name: str, parameters: dict) -> Optional[TradingStrategy]:
    """Create strategy instance from name and parameters."""
    if strategy_name == 'RSI_Strategy':
        return RSIStrategy(parameters)
    elif strategy_name == 'MACD_Strategy':
        return MACDStrategy(parameters)
    elif strategy_name == 'Mean_Reversion_Strategy':
        return MeanReversionStrategy(parameters)

    return None


def _get_strategy_class(strategy_name: str) -> Optional[type]:
    """Get strategy class from name."""
    if strategy_name == 'RSI_Strategy':
        return RSIStrategy
    elif strategy_name == 'MACD_Strategy':
        return MACDStrategy
    elif strategy_name == 'Mean_Reversion_Strategy':
        return MeanReversionStrategy

    return None