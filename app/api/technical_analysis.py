from flask import jsonify, request, current_app
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from datetime import datetime, timezone

from . import api_bp
from app.technical_analysis import technical_analysis_engine


def get_db_session():
    """Get database session."""
    engine = create_engine(current_app.config['SQLALCHEMY_DATABASE_URI'])
    return Session(engine)


@api_bp.route('/technical-analysis/<symbol>', methods=['GET'])
def get_technical_analysis(symbol):
    """
    Get technical analysis for a symbol.

    Query parameters:
    - indicators: comma-separated list of indicators (optional)
    """
    try:
        symbol = symbol.upper()
        indicators_param = request.args.get('indicators', '')
        indicators = indicators_param.split(',') if indicators_param else None

        analysis = technical_analysis_engine.get_technical_analysis(symbol, indicators)

        if 'error' in analysis:
            return jsonify(analysis), 404

        return jsonify(analysis), 200

    except Exception as e:
        current_app.logger.error(f"Technical analysis error: {e}")
        return jsonify({'error': 'Failed to get technical analysis'}), 500


@api_bp.route('/charts/<symbol>', methods=['GET'])
def get_chart_data(symbol):
    """
    Get chart data with technical indicators for frontend visualization.

    Query parameters:
    - timeframe: 1D, 1W, 1M (default: 1D)
    - periods: number of periods to return (default: 100)
    """
    try:
        symbol = symbol.upper()
        timeframe = request.args.get('timeframe', '1D')
        periods = int(request.args.get('periods', 100))

        chart_data = technical_analysis_engine.get_chart_data(symbol, timeframe, periods)

        if 'error' in chart_data:
            return jsonify(chart_data), 404

        return jsonify(chart_data), 200

    except Exception as e:
        current_app.logger.error(f"Chart data error: {e}")
        return jsonify({'error': 'Failed to get chart data'}), 500


@api_bp.route('/indicators/<symbol>/<indicator>', methods=['GET'])
def get_indicator_data(symbol, indicator):
    """
    Get specific indicator data for a symbol.

    Supported indicators: sma, ema, rsi, macd, bollinger, stochastic, atr, momentum

    Query parameters:
    - period: indicator period (default varies by indicator)
    - periods: number of data points to return (default: 50)
    """
    try:
        symbol = symbol.upper()
        indicator = indicator.lower()
        period = int(request.args.get('period', 14))
        periods = int(request.args.get('periods', 50))

        # Get price data
        price_data = technical_analysis_engine._get_price_data(symbol)
        if not price_data:
            return jsonify({'error': f'No price data available for {symbol}'}), 404

        closes = [p.close for p in price_data[-periods:]]
        highs = [p.high for p in price_data[-periods:]]
        lows = [p.low for p in price_data[-periods:]]

        result = {
            'symbol': symbol,
            'indicator': indicator,
            'period': period,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': []
        }

        if indicator == 'sma':
            values = technical_analysis_engine.sma(closes, period)
            result['data'] = [float(v) if v is not None else None for v in values]

        elif indicator == 'ema':
            values = technical_analysis_engine.ema(closes, period)
            result['data'] = [float(v) if v is not None else None for v in values]

        elif indicator == 'rsi':
            values = technical_analysis_engine.rsi(closes, period)
            result['data'] = [float(v) if v is not None else None for v in values]

        elif indicator == 'macd':
            fast_period = int(request.args.get('fast_period', 12))
            slow_period = int(request.args.get('slow_period', 26))
            signal_period = int(request.args.get('signal_period', 9))

            macd_line, signal_line, histogram = technical_analysis_engine.macd(
                closes, fast_period, slow_period, signal_period
            )

            result['data'] = {
                'macd_line': [float(v) if v is not None else None for v in macd_line],
                'signal_line': [float(v) if v is not None else None for v in signal_line],
                'histogram': [float(v) if v is not None else None for v in histogram]
            }

        elif indicator == 'bollinger':
            std_dev = float(request.args.get('std_dev', 2.0))
            sma, upper, lower = technical_analysis_engine.bollinger_bands(closes, period, std_dev)

            result['data'] = {
                'sma': [float(v) if v is not None else None for v in sma],
                'upper': [float(v) if v is not None else None for v in upper],
                'lower': [float(v) if v is not None else None for v in lower]
            }

        elif indicator == 'stochastic':
            k_period = period
            d_period = int(request.args.get('d_period', 3))

            k_line, d_line = technical_analysis_engine.stochastic_oscillator(
                highs, lows, closes, k_period, d_period
            )

            result['data'] = {
                'k': [float(v) if v is not None else None for v in k_line],
                'd': [float(v) if v is not None else None for v in d_line]
            }

        elif indicator == 'atr':
            values = technical_analysis_engine.atr(highs, lows, closes, period)
            result['data'] = [float(v) if v is not None else None for v in values]

        elif indicator == 'momentum':
            # Use ChartAnalysis for momentum
            momentum_values = technical_analysis_engine.calculate_momentum(price_data[-periods:], period)
            result['data'] = [float(v) if v is not None else None for v in momentum_values]

        else:
            return jsonify({'error': f'Unsupported indicator: {indicator}'}), 400

        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f"Indicator data error: {e}")
        return jsonify({'error': 'Failed to get indicator data'}), 500


@api_bp.route('/support-resistance/<symbol>', methods=['GET'])
def get_support_resistance(symbol):
    """
    Get support and resistance levels for a symbol.

    Query parameters:
    - lookback_periods: number of periods to analyze (default: 20)
    - tolerance: grouping tolerance as percentage (default: 0.02)
    """
    try:
        symbol = symbol.upper()
        lookback_periods = int(request.args.get('lookback_periods', 20))
        tolerance = float(request.args.get('tolerance', 0.02))

        # Get price data
        price_data = technical_analysis_engine._get_price_data(symbol)
        if not price_data:
            return jsonify({'error': f'No price data available for {symbol}'}), 404

        from app.technical_analysis import ChartAnalysis
        levels = ChartAnalysis.detect_support_resistance(price_data, lookback_periods, tolerance)

        result = {
            'symbol': symbol,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'lookback_periods': lookback_periods,
            'tolerance': tolerance,
            'support_levels': [float(level) for level in levels['support']],
            'resistance_levels': [float(level) for level in levels['resistance']]
        }

        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f"Support/resistance error: {e}")
        return jsonify({'error': 'Failed to calculate support/resistance levels'}), 500


@api_bp.route('/fibonacci/<symbol>', methods=['GET'])
def get_fibonacci_levels(symbol):
    """
    Calculate Fibonacci retracement levels for a symbol.

    Query parameters:
    - lookback_periods: number of periods to find high/low (default: 20)
    """
    try:
        symbol = symbol.upper()
        lookback_periods = int(request.args.get('lookback_periods', 20))

        # Get price data
        price_data = technical_analysis_engine._get_price_data(symbol)
        if not price_data:
            return jsonify({'error': f'No price data available for {symbol}'}), 404

        # Find high and low in lookback period
        recent_prices = price_data[-lookback_periods:]
        high_price = max(p.high for p in recent_prices)
        low_price = min(p.low for p in recent_prices)

        from app.technical_analysis import TechnicalIndicators
        fib_levels = TechnicalIndicators.fibonacci_retracement(high_price, low_price)

        result = {
            'symbol': symbol,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'lookback_periods': lookback_periods,
            'high_price': float(high_price),
            'low_price': float(low_price),
            'fibonacci_levels': {k: float(v) for k, v in fib_levels.items()}
        }

        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f"Fibonacci levels error: {e}")
        return jsonify({'error': 'Failed to calculate Fibonacci levels'}), 500


@api_bp.route('/pivot-points/<symbol>', methods=['GET'])
def get_pivot_points(symbol):
    """
    Calculate pivot points and support/resistance levels for a symbol.
    """
    try:
        symbol = symbol.upper()

        # Get current price data (use last 3 periods for HLC)
        price_data = technical_analysis_engine._get_price_data(symbol)
        if len(price_data) < 3:
            return jsonify({'error': f'Insufficient price data for {symbol}'}), 404

        # Use last 3 periods for pivot calculation
        recent_prices = price_data[-3:]
        high_price = max(p.high for p in recent_prices)
        low_price = min(p.low for p in recent_prices)
        close_price = recent_prices[-1].close

        from app.technical_analysis import TechnicalIndicators
        pivot_levels = TechnicalIndicators.pivot_points(high_price, low_price, close_price)

        result = {
            'symbol': symbol,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'high_price': float(high_price),
            'low_price': float(low_price),
            'close_price': float(close_price),
            'pivot_levels': {k: float(v) for k, v in pivot_levels.items()}
        }

        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f"Pivot points error: {e}")
        return jsonify({'error': 'Failed to calculate pivot points'}), 500


@api_bp.route('/signals/<symbol>', methods=['GET'])
def get_trading_signals(symbol):
    """
    Get trading signals based on technical analysis.

    Query parameters:
    - indicators: comma-separated list of indicators to analyze (optional)
    - min_strength: minimum signal strength (WEAK, MEDIUM, STRONG) (default: WEAK)
    """
    try:
        symbol = symbol.upper()
        indicators_param = request.args.get('indicators', '')
        indicators = indicators_param.split(',') if indicators_param else None
        min_strength = request.args.get('min_strength', 'WEAK').upper()

        strength_levels = {'WEAK': 0, 'MEDIUM': 1, 'STRONG': 2}
        min_strength_level = strength_levels.get(min_strength, 0)

        analysis = technical_analysis_engine.get_technical_analysis(symbol, indicators)

        if 'error' in analysis:
            return jsonify(analysis), 404

        # Filter signals by minimum strength
        filtered_signals = []
        for signal in analysis.get('signals', []):
            signal_strength = strength_levels.get(signal.get('strength', 'WEAK'), 0)
            if signal_strength >= min_strength_level:
                filtered_signals.append(signal)

        result = {
            'symbol': symbol,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_signals': len(analysis.get('signals', [])),
            'filtered_signals': len(filtered_signals),
            'min_strength': min_strength,
            'signals': filtered_signals,
            'trend': analysis.get('trend')
        }

        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f"Trading signals error: {e}")
        return jsonify({'error': 'Failed to get trading signals'}), 500


@api_bp.route('/multi-analysis', methods=['POST'])
def get_multi_symbol_analysis():
    """
    Get technical analysis for multiple symbols.

    Request body:
    {
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "indicators": ["rsi", "macd", "sma"],
        "analysis_type": "signals"  // or "indicators", "full"
    }
    """
    try:
        data = request.get_json()

        if not data or 'symbols' not in data:
            return jsonify({'error': 'symbols array required'}), 400

        symbols = [s.upper() for s in data['symbols']]
        indicators = data.get('indicators', ['rsi', 'macd'])
        analysis_type = data.get('analysis_type', 'signals')

        results = {}

        for symbol in symbols:
            try:
                analysis = technical_analysis_engine.get_technical_analysis(symbol, indicators)

                if analysis_type == 'signals':
                    results[symbol] = {
                        'signals': analysis.get('signals', []),
                        'trend': analysis.get('trend')
                    }
                elif analysis_type == 'indicators':
                    results[symbol] = analysis.get('indicators', {})
                else:  # full
                    results[symbol] = analysis

            except Exception as e:
                results[symbol] = {'error': str(e)}

        return jsonify({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'analysis_type': analysis_type,
            'results': results
        }), 200

    except Exception as e:
        current_app.logger.error(f"Multi-analysis error: {e}")
        return jsonify({'error': 'Failed to perform multi-symbol analysis'}), 500