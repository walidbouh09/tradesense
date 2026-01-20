"""
Comprehensive tests for Access Control System

Tests challenge-based trading restrictions and role-based permissions.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from app.access_control import (
    access_control,
    Permission,
    AccessDeniedReason,
    require_active_challenge,
    require_permission
)


class TestPermissions:
    """Test permission system."""
    
    def test_user_permissions(self):
        """Test USER role permissions."""
        perms = access_control.get_user_permissions('USER')
        
        assert 'view_challenges' in perms
        assert 'create_challenge' in perms
        assert 'trade' in perms
        assert 'view_analytics' in perms
        assert 'admin_access' not in perms
    
    def test_admin_permissions(self):
        """Test ADMIN role permissions."""
        perms = access_control.get_user_permissions('ADMIN')
        
        assert 'view_challenges' in perms
        assert 'create_challenge' in perms
        assert 'trade' in perms
        assert 'view_analytics' in perms
        assert 'admin_access' in perms
    
    def test_superadmin_permissions(self):
        """Test SUPERADMIN role permissions."""
        perms = access_control.get_user_permissions('SUPERADMIN')
        
        assert 'view_challenges' in perms
        assert 'admin_access' in perms
    
    def test_has_permission(self):
        """Test permission checking."""
        assert access_control.has_permission('USER', Permission.TRADE) is True
        assert access_control.has_permission('USER', Permission.ADMIN_ACCESS) is False
        assert access_control.has_permission('ADMIN', Permission.ADMIN_ACCESS) is True
    
    def test_invalid_role(self):
        """Test invalid role returns empty permissions."""
        perms = access_control.get_user_permissions('INVALID_ROLE')
        assert perms == []


class TestChallengeAccess:
    """Test challenge-based access control."""
    
    @patch('app.access_control.AccessControlService.get_db_session')
    def test_no_active_challenge(self, mock_get_session):
        """Test access denied when no active challenge."""
        # Mock database to return no challenge
        mock_session = Mock()
        mock_session.execute.return_value.fetchone.return_value = None
        mock_session.close = Mock()
        mock_get_session.return_value = mock_session
        
        can_trade, reason, message = access_control.can_trade('user-123')
        
        assert can_trade is False
        assert reason == AccessDeniedReason.NO_ACTIVE_CHALLENGE
        assert 'No active challenge' in message
    
    @patch('app.access_control.AccessControlService.get_db_session')
    def test_challenge_not_paid(self, mock_get_session):
        """Test access denied when challenge payment not completed."""
        # Mock database to return unpaid challenge
        mock_result = Mock()
        mock_result.id = 'challenge-123'
        mock_result.status = 'ACTIVE'
        mock_result.challenge_type = 'STARTER'
        mock_result.initial_balance = 10000.0
        mock_result.current_equity = 10000.0
        mock_result.started_at = datetime.now(timezone.utc)
        mock_result.ended_at = None
        mock_result.created_at = datetime.now(timezone.utc)
        mock_result.payment_status = 'PENDING'  # Not paid
        mock_result.payment_amount = 200.0
        mock_result.payment_provider = 'CMI'
        
        mock_session = Mock()
        mock_session.execute.return_value.fetchone.return_value = mock_result
        mock_session.close = Mock()
        mock_get_session.return_value = mock_session
        
        can_trade, reason, message = access_control.can_trade('user-123')
        
        assert can_trade is False
        assert reason == AccessDeniedReason.PAYMENT_REQUIRED
        assert 'payment not completed' in message
    
    @patch('app.access_control.AccessControlService.get_db_session')
    def test_challenge_not_started(self, mock_get_session):
        """Test access denied when challenge not started."""
        mock_result = Mock()
        mock_result.id = 'challenge-123'
        mock_result.status = 'ACTIVE'
        mock_result.challenge_type = 'STARTER'
        mock_result.initial_balance = 10000.0
        mock_result.current_equity = 10000.0
        mock_result.started_at = None  # Not started
        mock_result.ended_at = None
        mock_result.created_at = datetime.now(timezone.utc)
        mock_result.payment_status = 'SUCCESS'
        mock_result.payment_amount = 200.0
        mock_result.payment_provider = 'CMI'
        
        mock_session = Mock()
        mock_session.execute.return_value.fetchone.return_value = mock_result
        mock_session.close = Mock()
        mock_get_session.return_value = mock_session
        
        can_trade, reason, message = access_control.can_trade('user-123')
        
        assert can_trade is False
        assert reason == AccessDeniedReason.CHALLENGE_NOT_STARTED
        assert 'not started' in message
    
    @patch('app.access_control.AccessControlService.get_db_session')
    def test_challenge_ended(self, mock_get_session):
        """Test access denied when challenge has ended."""
        mock_result = Mock()
        mock_result.id = 'challenge-123'
        mock_result.status = 'ACTIVE'
        mock_result.challenge_type = 'STARTER'
        mock_result.initial_balance = 10000.0
        mock_result.current_equity = 10000.0
        mock_result.started_at = datetime.now(timezone.utc)
        mock_result.ended_at = datetime.now(timezone.utc)  # Ended
        mock_result.created_at = datetime.now(timezone.utc)
        mock_result.payment_status = 'SUCCESS'
        mock_result.payment_amount = 200.0
        mock_result.payment_provider = 'CMI'
        
        mock_session = Mock()
        mock_session.execute.return_value.fetchone.return_value = mock_result
        mock_session.close = Mock()
        mock_get_session.return_value = mock_session
        
        can_trade, reason, message = access_control.can_trade('user-123')
        
        assert can_trade is False
        assert reason == AccessDeniedReason.CHALLENGE_ENDED
        assert 'ended' in message
    
    @patch('app.access_control.AccessControlService.get_db_session')
    def test_valid_active_challenge(self, mock_get_session):
        """Test access granted with valid active challenge."""
        mock_result = Mock()
        mock_result.id = 'challenge-123'
        mock_result.status = 'ACTIVE'
        mock_result.challenge_type = 'STARTER'
        mock_result.initial_balance = 10000.0
        mock_result.current_equity = 10000.0
        mock_result.started_at = datetime.now(timezone.utc)
        mock_result.ended_at = None
        mock_result.created_at = datetime.now(timezone.utc)
        mock_result.payment_status = 'SUCCESS'
        mock_result.payment_amount = 200.0
        mock_result.payment_provider = 'CMI'
        
        mock_session = Mock()
        mock_session.execute.return_value.fetchone.return_value = mock_result
        mock_session.close = Mock()
        mock_get_session.return_value = mock_session
        
        can_trade, reason, message = access_control.can_trade('user-123')
        
        assert can_trade is True
        assert reason is None
        assert message is None


class TestUserAccountStatus:
    """Test user account status checking."""
    
    @patch('app.access_control.AccessControlService.get_db_session')
    def test_active_user(self, mock_get_session):
        """Test active user account."""
        mock_result = Mock()
        mock_result.status = 'ACTIVE'
        mock_result.deleted_at = None
        
        mock_session = Mock()
        mock_session.execute.return_value.fetchone.return_value = mock_result
        mock_session.close = Mock()
        mock_get_session.return_value = mock_session
        
        is_active, reason = access_control.check_user_active('user-123')
        
        assert is_active is True
        assert reason is None
    
    @patch('app.access_control.AccessControlService.get_db_session')
    def test_deleted_user(self, mock_get_session):
        """Test deleted user account."""
        mock_result = Mock()
        mock_result.status = 'ACTIVE'
        mock_result.deleted_at = datetime.now(timezone.utc)
        
        mock_session = Mock()
        mock_session.execute.return_value.fetchone.return_value = mock_result
        mock_session.close = Mock()
        mock_get_session.return_value = mock_session
        
        is_active, reason = access_control.check_user_active('user-123')
        
        assert is_active is False
        assert reason == 'Account deleted'
    
    @patch('app.access_control.AccessControlService.get_db_session')
    def test_suspended_user(self, mock_get_session):
        """Test suspended user account."""
        mock_result = Mock()
        mock_result.status = 'SUSPENDED'
        mock_result.deleted_at = None
        
        mock_session = Mock()
        mock_session.execute.return_value.fetchone.return_value = mock_result
        mock_session.close = Mock()
        mock_get_session.return_value = mock_session
        
        is_active, reason = access_control.check_user_active('user-123')
        
        assert is_active is False
        assert 'SUSPENDED' in reason


class TestEnforceTradingAccess:
    """Test trading access enforcement."""
    
    @patch('app.access_control.AccessControlService.can_trade')
    @patch('app.access_control.AccessControlService.get_active_challenge')
    def test_enforce_access_granted(self, mock_get_challenge, mock_can_trade):
        """Test access enforcement when trading is allowed."""
        mock_can_trade.return_value = (True, None, None)
        mock_get_challenge.return_value = {
            'id': 'challenge-123',
            'status': 'ACTIVE',
            'payment_status': 'SUCCESS'
        }
        
        result = access_control.enforce_trading_access('user-123')
        
        assert result['allowed'] is True
        assert 'challenge' in result
        assert result['message'] == 'Trading access granted'
    
    @patch('app.access_control.AccessControlService.can_trade')
    def test_enforce_access_denied(self, mock_can_trade):
        """Test access enforcement when trading is denied."""
        mock_can_trade.return_value = (
            False,
            AccessDeniedReason.NO_ACTIVE_CHALLENGE,
            'No active challenge found'
        )
        
        result = access_control.enforce_trading_access('user-123')
        
        assert result['allowed'] is False
        assert result['reason'] == 'no_active_challenge'
        assert 'action_required' in result


class TestDecoratorProtection:
    """Test decorator-based endpoint protection."""
    
    def test_require_active_challenge_decorator(self):
        """Test @require_active_challenge decorator."""
        from flask import Flask, request as flask_request
        
        app = Flask(__name__)
        
        @app.route('/test-trade', methods=['POST'])
        @require_active_challenge
        def test_trade():
            return {'success': True}
        
        # Test without user_id
        with app.test_client() as client:
            response = client.post('/test-trade', json={})
            assert response.status_code == 401
            data = response.get_json()
            assert 'User ID required' in data['error']
    
    @patch('app.access_control.access_control.enforce_trading_access')
    def test_require_active_challenge_with_access(self, mock_enforce):
        """Test decorator with valid access."""
        from flask import Flask
        
        mock_enforce.return_value = {
            'allowed': True,
            'challenge': {'id': 'challenge-123'},
            'message': 'Access granted'
        }
        
        app = Flask(__name__)
        
        @app.route('/test-trade', methods=['POST'])
        @require_active_challenge
        def test_trade():
            return {'success': True}
        
        with app.test_client() as client:
            response = client.post('/test-trade', json={'user_id': 'user-123'})
            assert response.status_code == 200
    
    @patch('app.access_control.access_control.enforce_trading_access')
    def test_require_active_challenge_without_access(self, mock_enforce):
        """Test decorator without valid access."""
        from flask import Flask
        
        mock_enforce.return_value = {
            'allowed': False,
            'reason': 'no_active_challenge',
            'message': 'No active challenge',
            'action_required': 'Purchase a challenge'
        }
        
        app = Flask(__name__)
        
        @app.route('/test-trade', methods=['POST'])
        @require_active_challenge
        def test_trade():
            return {'success': True}
        
        with app.test_client() as client:
            response = client.post('/test-trade', json={'user_id': 'user-123'})
            assert response.status_code == 403
            data = response.get_json()
            assert 'No active challenge' in data['error']


class TestChallengeOwnership:
    """Test challenge ownership validation."""
    
    @patch('app.access_control.AccessControlService.get_db_session')
    def test_user_owns_challenge(self, mock_get_session):
        """Test user owns the challenge."""
        mock_result = Mock()
        mock_result.user_id = 'user-123'
        
        mock_session = Mock()
        mock_session.execute.return_value.fetchone.return_value = mock_result
        mock_session.close = Mock()
        mock_get_session.return_value = mock_session
        
        can_access, reason = access_control.can_access_challenge('user-123', 'challenge-123')
        
        assert can_access is True
        assert reason is None
    
    @patch('app.access_control.AccessControlService.get_db_session')
    def test_user_does_not_own_challenge(self, mock_get_session):
        """Test user does not own the challenge."""
        mock_result = Mock()
        mock_result.user_id = 'other-user'
        
        mock_session = Mock()
        mock_session.execute.return_value.fetchone.return_value = mock_result
        mock_session.close = Mock()
        mock_get_session.return_value = mock_session
        
        can_access, reason = access_control.can_access_challenge('user-123', 'challenge-123')
        
        assert can_access is False
        assert 'permission' in reason
    
    @patch('app.access_control.AccessControlService.get_db_session')
    def test_challenge_not_found(self, mock_get_session):
        """Test challenge not found."""
        mock_session = Mock()
        mock_session.execute.return_value.fetchone.return_value = None
        mock_session.close = Mock()
        mock_get_session.return_value = mock_session
        
        can_access, reason = access_control.can_access_challenge('user-123', 'challenge-123')
        
        assert can_access is False
        assert 'not found' in reason


class TestAccessControlIntegration:
    """Test access control integration scenarios."""
    
    @patch('app.access_control.AccessControlService.get_db_session')
    def test_complete_access_flow(self, mock_get_session):
        """Test complete access control flow."""
        # Setup: User with active, paid, started challenge
        mock_result = Mock()
        mock_result.id = 'challenge-123'
        mock_result.status = 'ACTIVE'
        mock_result.challenge_type = 'STARTER'
        mock_result.initial_balance = 10000.0
        mock_result.current_equity = 10000.0
        mock_result.started_at = datetime.now(timezone.utc)
        mock_result.ended_at = None
        mock_result.created_at = datetime.now(timezone.utc)
        mock_result.payment_status = 'SUCCESS'
        mock_result.payment_amount = 200.0
        mock_result.payment_provider = 'CMI'
        
        mock_session = Mock()
        mock_session.execute.return_value.fetchone.return_value = mock_result
        mock_session.close = Mock()
        mock_get_session.return_value = mock_session
        
        # 1. Check if user can trade
        can_trade, reason, message = access_control.can_trade('user-123')
        assert can_trade is True
        
        # 2. Get active challenge
        challenge = access_control.get_active_challenge('user-123')
        assert challenge is not None
        assert challenge['id'] == 'challenge-123'
        
        # 3. Enforce trading access
        access_status = access_control.enforce_trading_access('user-123')
        assert access_status['allowed'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
