"""
Access Control API Endpoints

Endpoints for checking trading access and permissions.
"""

from flask import jsonify, request, current_app

from . import api_bp
from app.access_control import access_control, Permission


@api_bp.route('/access/can-trade/<user_id>', methods=['GET'])
def check_trading_access(user_id: str):
    """
    Check if user can execute trades.
    
    Args:
        user_id: User identifier
        
    Returns:
        Trading access status with details
    """
    try:
        access_status = access_control.enforce_trading_access(user_id)
        
        return jsonify(access_status), 200 if access_status['allowed'] else 403
        
    except Exception as e:
        current_app.logger.error(f"Error checking trading access: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/access/active-challenge/<user_id>', methods=['GET'])
def get_active_challenge(user_id: str):
    """
    Get user's active challenge.
    
    Args:
        user_id: User identifier
        
    Returns:
        Active challenge data or null
    """
    try:
        challenge = access_control.get_active_challenge(user_id)
        
        if not challenge:
            return jsonify({
                'active_challenge': None,
                'message': 'No active challenge found'
            }), 200
        
        return jsonify({
            'active_challenge': challenge,
            'message': 'Active challenge found'
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting active challenge: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/access/permissions/<user_role>', methods=['GET'])
def get_user_permissions(user_role: str):
    """
    Get permissions for a user role.
    
    Args:
        user_role: User role (USER, ADMIN, SUPERADMIN)
        
    Returns:
        List of permissions
    """
    try:
        permissions = access_control.get_user_permissions(user_role.upper())
        
        return jsonify({
            'role': user_role.upper(),
            'permissions': permissions
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting permissions: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/access/check-permission', methods=['POST'])
def check_permission():
    """
    Check if user has a specific permission.
    
    Request body:
    {
        "user_role": "USER|ADMIN|SUPERADMIN",
        "permission": "view_challenges|create_challenge|trade|view_analytics|admin_access"
    }
    
    Returns:
        Permission check result
    """
    try:
        data = request.get_json()
        
        if not data or 'user_role' not in data or 'permission' not in data:
            return jsonify({'error': 'user_role and permission are required'}), 400
        
        user_role = data['user_role'].upper()
        permission_str = data['permission']
        
        try:
            permission = Permission(permission_str)
        except ValueError:
            return jsonify({
                'error': f'Invalid permission. Must be one of: {", ".join([p.value for p in Permission])}'
            }), 400
        
        has_permission = access_control.has_permission(user_role, permission)
        
        return jsonify({
            'role': user_role,
            'permission': permission_str,
            'has_permission': has_permission
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error checking permission: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/access/account-status/<user_id>', methods=['GET'])
def check_account_status(user_id: str):
    """
    Check user account status.
    
    Args:
        user_id: User identifier
        
    Returns:
        Account status
    """
    try:
        is_active, reason = access_control.check_user_active(user_id)
        
        return jsonify({
            'user_id': user_id,
            'is_active': is_active,
            'reason': reason,
            'message': 'Account is active' if is_active else f'Account inactive: {reason}'
        }), 200 if is_active else 403
        
    except Exception as e:
        current_app.logger.error(f"Error checking account status: {e}")
        return jsonify({'error': str(e)}), 500
