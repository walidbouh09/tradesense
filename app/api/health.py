"""
Health Check Endpoint

Provides service health monitoring for load balancers and monitoring systems.
"""

from flask import jsonify
from . import api_bp


@api_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for load balancers and monitoring.

    Returns service status and basic health metrics.
    """
    return jsonify({
        'status': 'healthy',
        'service': 'tradesense-backend',
        'version': '1.0.0',
        'timestamp': '2024-01-18T00:27:00Z'
    }), 200